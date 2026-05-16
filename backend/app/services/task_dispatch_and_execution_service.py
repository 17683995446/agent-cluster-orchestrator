from typing import List, Optional, Dict
import uuid
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
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

class TaskService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.task_repo = TaskRepository(session)
        self.agent_repo = AgentRepository(session)

    async def create(self, data: TaskCreate) -> Task:
        task = Task(
            id=str(uuid.uuid4()),
            description=data.description,
            priority=data.priority,
            type=data.type.value if hasattr(data.type, 'value') else data.type,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow()
        )
        task = await self.task_repo.create(task)
        logger.info("task_created", task_id=task.id, priority=task.priority)
        
        asyncio.create_task(self.schedule_task(task.id))
        return task

    async def get(self, task_id: str) -> Task:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise TaskNotFoundError(task_id)
        return task

    async def get_all(self, skip: int = 0, limit: int = 100, status: Optional[TaskStatus] = None) -> tuple[List[Task], int]:
        tasks = await self.task_repo.get_all(skip, limit, status)
        total = await self.task_repo.count_total()
        return tasks, total

    async def cancel(self, task_id: str) -> bool:
        task = await self.get(task_id)
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False
        
        success = await self.task_repo.update_status(task_id, TaskStatus.CANCELLED)
        if task.assigned_agent_id:
            await self.agent_repo.update_status(task.assigned_agent_id, AgentStatus.IDLE)
        
        logger.info("task_cancelled", task_id=task_id)
        return success

    async def schedule_task(self, task_id: str) -> Optional[str]:
        task = await self.task_repo.get_by_id(task_id)
        if not task or task.status != TaskStatus.PENDING:
            return None

        agent = await self._select_agent(task)
        if not agent:
            logger.warning("no_idle_agent_available", task_id=task_id)
            return None

        await self.agent_repo.update_status(agent.id, AgentStatus.BUSY)
        await self.task_repo.assign_agent(task_id, agent.id)
        
        asyncio.create_task(self._execute_task(task_id, agent.id))
        return agent.id

    async def _select_agent(self, task) -> Optional[Agent]:
        idle_agents = await self.agent_repo.get_idle_agents()
        if not idle_agents:
            return None

        capabilities = self._infer_capabilities(task.description)
        for cap in capabilities:
            agents_with_cap = await self.agent_repo.get_by_capability(cap)
            available = [a for a in agents_with_cap if a.status == AgentStatus.IDLE]
            if available:
                return available[0]

        return idle_agents[0]

    def _infer_capabilities(self, description: str) -> List[str]:
        desc_lower = description.lower()
        capabilities = []
        
        capability_keywords = {
            "code_generation": ["代码", "写代码", "生成代码", "code", "programming"],
            "code_review": ["审查代码", "review", "代码审查"],
            "data_analysis": ["分析", "数据", "analysis", "data"],
            "writing": ["写作", "写文章", "article", "写", "write"],
            "translation": ["翻译", "translation", "translate"],
            "summarization": ["总结", "摘要", "summarize", "summary"],
        }
        
        for cap, keywords in capability_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                capabilities.append(cap)
        
        return capabilities

    async def _execute_task(self, task_id: str, agent_id: str):
        start_time = time.time()
        task = await self.task_repo.get_by_id(task_id)
        agent = await self.agent_repo.get_by_id(agent_id)
        
        if not task or not agent:
            return
        
        try:
            provider = llm_manager.get_provider(agent.provider)
            if not provider:
                raise ValueError(f"Provider '{agent.provider}' not available")
            
            result = await provider.generate(task.description, agent.model)
            
            await self.task_repo.set_result(task_id, {
                "content": result.get("content"),
                "model": result.get("model"),
                "usage": result.get("usage"),
                "agent_id": agent_id
            })
            
            await self.agent_repo.increment_stats(agent_id, success=True, response_time=time.time() - start_time)
            logger.info("task_completed", task_id=task_id, agent_id=agent_id, duration=time.time() - start_time)
            
        except Exception as e:
            await self.task_repo.set_error(task_id, str(e))
            await self.agent_repo.increment_stats(agent_id, success=False, response_time=time.time() - start_time)
            logger.error("task_failed", task_id=task_id, agent_id=agent_id, error=str(e))

    async def execute_cluster_task(self, data: ClusterExecuteRequest) -> Dict:
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
            asyncio.create_task(self.schedule_task(subtask.id))
        
        parent_task.subtask_ids = subtask_ids
        await self.task_repo.update(parent_task)
        
        logger.info("cluster_task_created", parent_id=parent_task.id, num_subtasks=len(subtask_ids))
        
        return {
            "parent_task_id": parent_task.id,
            "subtask_ids": subtask_ids,
            "status": "scheduled"
        }

    async def _decompose_task(self, task: str, num_parts: int) -> List[str]:
        provider = llm_manager.get_provider("openai")
        if not provider:
            return [f"{task} (Part {i+1})" for i in range(num_parts)]
        
        prompt = f"""将以下任务分解为{num_parts}个独立的子任务。
只返回子任务列表，每行一个任务，不需要编号。

任务: {task}"""
        
        try:
            result = await provider.generate(prompt, "gpt-3.5-turbo")
            content = result.get("content", "")
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            return lines[:num_parts] if lines else [task] * num_parts
        except Exception:
            return [f"{task} (Part {i+1})" for i in range(num_parts)]

    async def get_cluster_stats(self) -> ClusterStats:
        stats = ClusterStats()
        
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
        
        return stats
