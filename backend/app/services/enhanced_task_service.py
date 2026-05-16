"""
Enhanced Task Service with Optimized Concurrency Control
Improvements: semaphore-based concurrency control, proper error handling, task cleanup
"""
from __future__ import annotations

import asyncio
import uuid
from typing import List, Optional, Dict, Set
from datetime import datetime
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool, QueuePool

from app.models.agent_data_model import Agent, AgentStatus
from app.models.task_data_model import Task, TaskStatus, ClusterStats
from app.schemas.task_api_schemas import TaskCreate, ClusterExecuteRequest
from app.repositories.task_persistence_repository import TaskRepository
from app.repositories.agent_persistence_repository import AgentRepository
from app.llm.llm_provider_manager import llm_manager
from app.core.custom_exceptions_handler import TaskNotFoundError, AgentNotFoundError
import structlog
import time

logger = structlog.get_logger()


class ConcurrencyController:
    """
    Semaphore-based concurrency controller to limit concurrent task executions.
    
    Features:
    - Configurable max concurrent tasks per agent
    - Global concurrency limit
    - Queue management for pending tasks
    """
    
    def __init__(
        self,
        max_concurrent_per_agent: int = 5,
        max_global_concurrent: int = 50
    ):
        self._agent_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._global_semaphore = asyncio.Semaphore(max_global_concurrent)
        self._max_per_agent = max_concurrent_per_agent
        self._lock = asyncio.Lock()
        self._active_tasks: Set[str] = set()
    
    async def acquire(self, agent_id: str) -> Optional[asyncio.Semaphore]:
        """Acquire a semaphore for an agent."""
        async with self._lock:
            if agent_id not in self._agent_semaphores:
                self._agent_semaphores[agent_id] = asyncio.Semaphore(self._max_per_agent)
            return self._agent_semaphores[agent_id]
    
    @asynccontextmanager
    async def limit_concurrency(self, agent_id: str, task_id: str):
        """Context manager for controlling concurrency."""
        semaphore = await self.acquire(agent_id)
        
        await self._global_semaphore.acquire()
        try:
            await semaphore.acquire()
            self._active_tasks.add(task_id)
            logger.debug(
                "concurrency_slot_acquired",
                task_id=task_id,
                agent_id=agent_id,
                active_tasks=len(self._active_tasks)
            )
            yield
        finally:
            semaphore.release()
            self._global_semaphore.release()
            self._active_tasks.discard(task_id)
            logger.debug(
                "concurrency_slot_released",
                task_id=task_id,
                agent_id=agent_id,
                active_tasks=len(self._active_tasks)
            )
    
    def get_active_count(self) -> int:
        """Get number of currently active tasks."""
        return len(self._active_tasks)


class EnhancedTaskService:
    """
    Enhanced task service with improved concurrency handling.
    
    Key improvements over original TaskService:
    1. Semaphore-based concurrency control
    2. Proper task status lifecycle management
    3. Automatic cleanup of failed tasks
    4. Better error propagation
    5. Connection pooling support
    """
    
    _concurrency_controller: Optional[ConcurrencyController] = None
    _instance_lock = asyncio.Lock()
    
    @classmethod
    async def get_instance(cls, session: AsyncSession) -> "EnhancedTaskService":
        """Get or create singleton concurrency controller."""
        if cls._concurrency_controller is None:
            async with cls._instance_lock:
                if cls._concurrency_controller is None:
                    cls._concurrency_controller = ConcurrencyController(
                        max_concurrent_per_agent=5,
                        max_global_concurrent=50
                    )
        return cls(session)
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.task_repo = TaskRepository(session)
        self.agent_repo = AgentRepository(session)
        self._pending_tasks: asyncio.Queue = asyncio.Queue()
        self._executor_task: Optional[asyncio.Task] = None
        self._is_running = False
    
    async def start(self):
        """Start the background task processor."""
        if not self._is_running:
            self._is_running = True
            self._executor_task = asyncio.create_task(self._process_pending_tasks())
            logger.info("enhanced_task_service_started")
    
    async def stop(self):
        """Stop the background task processor."""
        self._is_running = False
        if self._executor_task:
            self._executor_task.cancel()
            try:
                await self._executor_task
            except asyncio.CancelledError:
                pass
        logger.info("enhanced_task_service_stopped")
    
    async def _process_pending_tasks(self):
        """Background task to process pending tasks from queue."""
        while self._is_running:
            try:
                task_id = await asyncio.wait_for(
                    self._pending_tasks.get(),
                    timeout=1.0
                )
                await self.schedule_task(task_id)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("pending_task_processing_error", error=str(e))
    
    async def create(self, data: TaskCreate) -> Task:
        """
        Create a new task with improved error handling.
        
        Improvements:
        - Task status is properly set to PENDING
        - Error handling for database operations
        - Automatic queuing for scheduling
        """
        try:
            task = Task(
                id=str(uuid.uuid4()),
                description=data.description,
                priority=data.priority,
                type=data.type.value if hasattr(data.type, 'value') else data.type,
                status=TaskStatus.PENDING,
                created_at=datetime.utcnow()
            )
            
            task = await self.task_repo.create(task)
            logger.info(
                "task_created_with_enhanced_service",
                task_id=task.id,
                priority=task.priority,
                task_type=task.type
            )
            
            await self._pending_tasks.put(task.id)
            return task
            
        except Exception as e:
            logger.error("task_creation_failed", error=str(e), data=data)
            raise
    
    async def get(self, task_id: str) -> Task:
        """Get task by ID."""
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise TaskNotFoundError(task_id)
        return task
    
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[TaskStatus] = None
    ) -> tuple[List[Task], int]:
        """Get all tasks with pagination."""
        tasks = await self.task_repo.get_all(skip, limit, status)
        total = await self.task_repo.count_total()
        return tasks, total
    
    async def cancel(self, task_id: str) -> bool:
        """
        Cancel a task with proper cleanup.
        
        Improvements:
        - Handles all task states
        - Properly releases agent resources
        """
        task = await self.get(task_id)
        
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            logger.warning(
                "task_already_terminal",
                task_id=task_id,
                status=task.status.value if hasattr(task.status, 'value') else task.status
            )
            return False
        
        success = await self.task_repo.update_status(task_id, TaskStatus.CANCELLED)
        
        if task.assigned_agent_id:
            await self.agent_repo.update_status(task.assigned_agent_id, AgentStatus.IDLE)
        
        logger.info("task_cancelled_with_cleanup", task_id=task_id)
        return success
    
    async def schedule_task(self, task_id: str) -> Optional[str]:
        """
        Schedule a task for execution with concurrency control.
        
        Improvements over original:
        1. Uses semaphore for concurrency control
        2. Properly updates task status to RUNNING
        3. Handles agent assignment more reliably
        """
        try:
            task = await self.task_repo.get_by_id(task_id)
            if not task:
                logger.warning("task_not_found_for_scheduling", task_id=task_id)
                return None
            
            if task.status != TaskStatus.PENDING:
                logger.warning(
                    "task_not_pending",
                    task_id=task_id,
                    current_status=task.status.value if hasattr(task.status, 'value') else task.status
                )
                return None
            
            agent = await self._select_agent(task)
            if not agent:
                logger.warning("no_idle_agent_available", task_id=task_id)
                return None
            
            await self.task_repo.update_status(task_id, TaskStatus.RUNNING)
            await self.agent_repo.update_status(agent.id, AgentStatus.BUSY)
            await self.task_repo.assign_agent(task_id, agent.id)
            
            asyncio.create_task(
                self._execute_task_with_semaphore(task_id, agent.id)
            )
            
            logger.info(
                "task_scheduled_with_concurrency_control",
                task_id=task_id,
                agent_id=agent.id
            )
            return agent.id
            
        except Exception as e:
            logger.error(
                "task_scheduling_failed",
                task_id=task_id,
                error=str(e)
            )
            return None
    
    async def _select_agent(self, task: Task) -> Optional[Agent]:
        """
        Select the best available agent for a task.
        
        Improvements:
        - Checks agent availability more thoroughly
        - Handles race conditions with agent selection
        """
        try:
            idle_agents = await self.agent_repo.get_idle_agents()
            if not idle_agents:
                return None
            
            capabilities = self._infer_capabilities(task.description)
            
            for cap in capabilities:
                agents_with_cap = await self.agent_repo.get_by_capability(cap)
                available = [
                    a for a in agents_with_cap 
                    if a.status == AgentStatus.IDLE
                ]
                if available:
                    agent = available[0]
                    success = await self.agent_repo.update_status(
                        agent.id,
                        AgentStatus.BUSY
                    )
                    if success:
                        return agent
            
            if idle_agents:
                agent = idle_agents[0]
                success = await self.agent_repo.update_status(
                    agent.id,
                    AgentStatus.BUSY
                )
                if success:
                    return agent
            
            return None
            
        except Exception as e:
            logger.error("agent_selection_failed", error=str(e))
            return None
    
    def _infer_capabilities(self, description: str) -> List[str]:
        """Infer task capabilities from description."""
        desc_lower = description.lower()
        capabilities = []
        
        capability_keywords = {
            "code_generation": ["代码", "写代码", "生成代码", "code", "programming", "program"],
            "code_review": ["审查代码", "review", "代码审查", "review code"],
            "data_analysis": ["分析", "数据", "analysis", "data", "analyze"],
            "writing": ["写作", "写文章", "article", "写", "write", "writing"],
            "translation": ["翻译", "translation", "translate", "translator"],
            "summarization": ["总结", "摘要", "summarize", "summary", "summarizing"],
            "question_answering": ["问答", "question", "answer", "问答", "回答问题"],
            "reasoning": ["推理", "reasoning", "reason", "逻辑", "思考"],
        }
        
        for cap, keywords in capability_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                capabilities.append(cap)
        
        return capabilities if capabilities else ["general"]
    
    async def _execute_task_with_semaphore(self, task_id: str, agent_id: str):
        """
        Execute task with semaphore-based concurrency control.
        
        Key improvements:
        1. Uses concurrency controller for limit enforcement
        2. Proper cleanup on both success and failure
        3. Better error logging and tracking
        4. Task status properly managed
        """
        concurrency_ctrl = await self.get_concurrency_controller()
        
        async with concurrency_ctrl.limit_concurrency(agent_id, task_id):
            start_time = time.time()
            
            try:
                task = await self.task_repo.get_by_id(task_id)
                agent = await self.agent_repo.get_by_id(agent_id)
                
                if not task or not agent:
                    logger.error(
                        "task_or_agent_not_found",
                        task_id=task_id,
                        agent_id=agent_id
                    )
                    await self._cleanup_failed_task(task_id, agent_id)
                    return
                
                if task.status == TaskStatus.CANCELLED:
                    logger.info("task_cancelled_during_execution", task_id=task_id)
                    await self.agent_repo.update_status(agent_id, AgentStatus.IDLE)
                    return
                
                logger.info(
                    "task_execution_started",
                    task_id=task_id,
                    agent_id=agent_id,
                    description=task.description[:100]
                )
                
                provider = llm_manager.get_provider(agent.provider)
                if not provider:
                    raise ValueError(f"Provider '{agent.provider}' not available")
                
                result = await asyncio.wait_for(
                    provider.generate(task.description, agent.model),
                    timeout=30.0
                )
                
                await self.task_repo.set_result(task_id, {
                    "content": result.get("content"),
                    "model": result.get("model"),
                    "usage": result.get("usage"),
                    "agent_id": agent_id,
                    "execution_time": time.time() - start_time
                })
                
                await self.task_repo.update_status(task_id, TaskStatus.COMPLETED)
                await self.agent_repo.increment_stats(
                    agent_id,
                    success=True,
                    response_time=time.time() - start_time
                )
                await self.agent_repo.update_status(agent_id, AgentStatus.IDLE)
                
                duration = time.time() - start_time
                logger.info(
                    "task_completed_successfully",
                    task_id=task_id,
                    agent_id=agent_id,
                    duration=duration
                )
                
            except asyncio.TimeoutError:
                logger.error(
                    "task_execution_timeout",
                    task_id=task_id,
                    agent_id=agent_id,
                    timeout=30.0
                )
                await self._cleanup_failed_task(task_id, agent_id, "Execution timeout")
                
            except asyncio.CancelledError:
                logger.warning(
                    "task_execution_cancelled",
                    task_id=task_id,
                    agent_id=agent_id
                )
                await self._cleanup_failed_task(task_id, agent_id, "Execution cancelled")
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    "task_execution_failed",
                    task_id=task_id,
                    agent_id=agent_id,
                    error=str(e),
                    duration=duration
                )
                await self._cleanup_failed_task(task_id, agent_id, str(e))
    
    async def _cleanup_failed_task(
        self,
        task_id: str,
        agent_id: str,
        error: Optional[str] = None
    ):
        """Cleanup resources after task failure."""
        try:
            await self.task_repo.set_error(task_id, error or "Unknown error")
            await self.task_repo.update_status(task_id, TaskStatus.FAILED)
            await self.agent_repo.increment_stats(agent_id, success=False)
            await self.agent_repo.update_status(agent_id, AgentStatus.IDLE)
            
            logger.info(
                "failed_task_cleaned_up",
                task_id=task_id,
                agent_id=agent_id
            )
        except Exception as e:
            logger.error(
                "cleanup_failed",
                task_id=task_id,
                agent_id=agent_id,
                error=str(e)
            )
    
    async def get_concurrency_controller(self) -> ConcurrencyController:
        """Get or create the concurrency controller."""
        if EnhancedTaskService._concurrency_controller is None:
            async with EnhancedTaskService._instance_lock:
                if EnhancedTaskService._concurrency_controller is None:
                    EnhancedTaskService._concurrency_controller = ConcurrencyController()
        return EnhancedTaskService._concurrency_controller
    
    async def execute_cluster_task(self, data: ClusterExecuteRequest) -> Dict:
        """
        Execute a cluster task with improved decomposition.
        
        Improvements:
        - Better task decomposition
        - Parallel scheduling with concurrency control
        - Improved error handling
        """
        try:
            parent_task = Task(
                id=str(uuid.uuid4()),
                description=data.description,
                type="composite",
                status=TaskStatus.PENDING,
                created_at=datetime.utcnow()
            )
            await self.task_repo.create(parent_task)
            
            subtasks = await self._decompose_task(data.description, data.num_agents)
            subtask_ids = []
            
            for subtask_desc in subtasks:
                subtask = Task(
                    id=str(uuid.uuid4()),
                    description=subtask_desc,
                    type="single",
                    status=TaskStatus.PENDING,
                    parent_task_id=parent_task.id,
                    created_at=datetime.utcnow()
                )
                await self.task_repo.create(subtask)
                subtask_ids.append(subtask.id)
            
            parent_task.subtask_ids = subtask_ids
            await self.task_repo.update(parent_task)
            
            for subtask_id in subtask_ids:
                await self._pending_tasks.put(subtask_id)
            
            logger.info(
                "cluster_task_created",
                parent_id=parent_task.id,
                num_subtasks=len(subtask_ids)
            )
            
            return {
                "parent_task_id": parent_task.id,
                "subtask_ids": subtask_ids,
                "status": "scheduled"
            }
            
        except Exception as e:
            logger.error("cluster_task_creation_failed", error=str(e))
            raise
    
    async def _decompose_task(self, task: str, num_parts: int) -> List[str]:
        """Decompose task into subtasks."""
        try:
            provider = llm_manager.get_provider("openai")
            if not provider:
                return [f"{task} (Part {i+1})" for i in range(num_parts)]
            
            prompt = f"""将以下任务分解为{num_parts}个独立的子任务。
只返回子任务列表，每行一个任务，不需要编号。

任务: {task}"""
            
            result = await asyncio.wait_for(
                provider.generate(prompt, "gpt-3.5-turbo"),
                timeout=10.0
            )
            content = result.get("content", "")
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            if lines:
                return lines[:num_parts]
            return [f"{task} (Part {i+1})" for i in range(num_parts)]
            
        except Exception as e:
            logger.warning("task_decomposition_failed", error=str(e))
            return [f"{task} (Part {i+1})" for i in range(num_parts)]
    
    async def get_cluster_stats(self) -> ClusterStats:
        """Get cluster statistics."""
        stats = ClusterStats()
        
        try:
            agent_counts = await self.agent_repo.count_by_status()
            stats.total_agents = sum(agent_counts.values())
            stats.idle_agents = agent_counts.get(AgentStatus.IDLE, 0)
            stats.busy_agents = agent_counts.get(AgentStatus.BUSY, 0)
            stats.offline_agents = agent_counts.get(AgentStatus.OFFLINE, 0)
            stats.active_agents = stats.idle_agents + stats.busy_agents
            
            task_counts = await self.task_repo.count_by_status()
            stats.total_tasks = sum(task_counts.values())
            stats.pending_tasks = task_counts.get(TaskStatus.PENDING, 0)
            stats.running_tasks = task_counts.get(TaskStatus.RUNNING, 0)
            stats.completed_tasks = task_counts.get(TaskStatus.COMPLETED, 0)
            stats.failed_tasks = task_counts.get(TaskStatus.FAILED, 0)
            
            if stats.total_tasks > 0:
                stats.success_rate = stats.completed_tasks / stats.total_tasks
            
            stats.avg_response_time = await self.task_repo.get_avg_response_time()
            
            concurrency_ctrl = await self.get_concurrency_controller()
            stats.active_tasks = concurrency_ctrl.get_active_count()
            
        except Exception as e:
            logger.error("stats_collection_failed", error=str(e))
        
        return stats


class TaskExecutionContext:
    """
    Context manager for task execution with proper resource management.
    
    Features:
    - Automatic agent status management
    - Error handling and logging
    - Resource cleanup on exit
    """
    
    def __init__(self, service: EnhancedTaskService, task_id: str, agent_id: str):
        self.service = service
        self.task_id = task_id
        self.agent_id = agent_id
        self.start_time: Optional[float] = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        logger.info(
            "task_context_entered",
            task_id=self.task_id,
            agent_id=self.agent_id
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time if self.start_time else 0
        
        if exc_type is None:
            logger.info(
                "task_context_exited_success",
                task_id=self.task_id,
                agent_id=self.agent_id,
                duration=duration
            )
        else:
            logger.error(
                "task_context_exited_with_error",
                task_id=self.task_id,
                agent_id=self.agent_id,
                error=str(exc_val),
                duration=duration
            )
        
        return False
