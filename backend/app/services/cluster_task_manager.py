"""
Phase 3: 任务分解与子任务协作执行
提供智能任务分解、子任务调度和结果聚合
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
from uuid import uuid4

import structlog

from app.models.task_data_model import Task, TaskStatus
from app.models.agent_data_model import Agent
from app.repositories.task_persistence_repository import TaskRepository
from app.repositories.agent_persistence_repository import AgentRepository
from app.services.agent_intelligent_router import IntelligentRouter, AgentCapability
from app.core.structured_logging_config import get_structured_logger
from app.llm.llm_provider_manager import llm_manager, LLMResponse

logger = get_structured_logger(__name__)


# ============== 数据模型定义 ==============

class SubtaskStatus(str, Enum):
    """子任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Subtask:
    """子任务定义"""
    subtask_id: str
    parent_task_id: str
    description: str
    status: SubtaskStatus = SubtaskStatus.PENDING
    assigned_agent_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    priority: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class TaskDecompositionResult:
    """任务分解结果"""
    parent_task_id: str
    subtasks: List[Subtask]
    decomposition_strategy: str
    explanation: str
    created_at: datetime = field(default_factory=datetime.utcnow)


class DecompositionStrategy(str, Enum):
    """任务分解策略"""
    STEP_BY_STEP = "step_by_step"
    PARALLEL = "parallel"
    DEPENDENCY_GRAPH = "dependency_graph"
    CAPABILITY_BASED = "capability_based"


# ============== 任务分解器 ==============

class TaskDecomposer:
    """
    任务智能分解器
    
    使用LLM将复杂任务分解为可管理的子任务
    """
    
    def __init__(self):
        self._decomposition_prompt = """
        作为任务分解专家，请将以下复杂任务分解为清晰、可执行的子任务。
        
        任务描述: {task_description}
        
        要求:
        1. 将任务分解为不超过{max_subtasks}个子任务
        2. 每个子任务应该是独立可执行的
        3. 考虑子任务之间的依赖关系
        4. 为每个子任务指定优先级 (1-5，5最高)
        
        请以JSON格式返回，结构如下:
        {{
            "subtasks": [
                {{
                    "description": "子任务描述",
                    "priority": 3,
                    "dependencies": ["其他子任务索引"],
                    "required_capability": "code_generation"
                }}
            ],
            "explanation": "分解说明",
            "strategy": "step_by_step|parallel|dependency_graph|capability_based"
        }}
        
        可用能力:
        - code_generation: 代码生成
        - code_review: 代码审查
        - data_analysis: 数据分析
        - text_generation: 文本生成
        - text_translation: 文本翻译
        - text_summarization: 文本摘要
        - question_answering: 问答
        - reasoning: 推理
        - general: 通用
        
        仅返回JSON，不要包含其他内容。
        """
    
    async def decompose(
        self,
        task: Task,
        max_subtasks: int = 10
    ) -> TaskDecompositionResult:
        """
        将任务分解为子任务
        
        Args:
            task: 父任务
            max_subtasks: 最大子任务数
            
        Returns:
            任务分解结果
        """
        logger.info(
            "decomposing_task",
            task_id=str(task.id),
            max_subtasks=max_subtasks
        )
        
        # 构建提示词
        prompt = self._decomposition_prompt.format(
            task_description=task.description,
            max_subtasks=max_subtasks
        )
        
        try:
            # 使用LLM进行分解
            response = await llm_manager.generate(
                prompt=prompt,
                provider="siliconflow" if hasattr(llm_manager, 'siliconflow_provider') else "openai"
            )
            
            # 解析响应
            result = self._parse_decomposition_response(response, str(task.id))
            
            logger.info(
                "task_decomposition_complete",
                task_id=str(task.id),
                subtask_count=len(result.subtasks)
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "task_decomposition_failed",
                task_id=str(task.id),
                error=str(e)
            )
            # 降级策略：简单分解
            return self._fallback_decomposition(task, max_subtasks)
    
    def _parse_decomposition_response(
        self,
        response: Any,
        parent_task_id: str
    ) -> TaskDecompositionResult:
        """解析分解响应"""
        try:
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 提取JSON部分
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                content = content[json_start:json_end]
            
            data = json.loads(content)
            
            # 创建子任务列表
            subtasks = []
            for i, subtask_data in enumerate(data.get("subtasks", [])):
                subtask = Subtask(
                    subtask_id=str(uuid4()),
                    parent_task_id=parent_task_id,
                    description=subtask_data.get("description", ""),
                    priority=subtask_data.get("priority", 1),
                    dependencies=[],
                    created_at=datetime.utcnow()
                )
                subtasks.append(subtask)
            
            return TaskDecompositionResult(
                parent_task_id=parent_task_id,
                subtasks=subtasks,
                decomposition_strategy=data.get("strategy", "step_by_step"),
                explanation=data.get("explanation", "")
            )
            
        except Exception as e:
            logger.error("failed_to_parse_decomposition", error=str(e))
            raise
    
    def _fallback_decomposition(
        self,
        task: Task,
        max_subtasks: int
    ) -> TaskDecompositionResult:
        """降级分解策略"""
        logger.info("using_fallback_decomposition", task_id=str(task.id))
        
        # 创建简单的分步子任务
        subtasks = [
            Subtask(
                subtask_id=str(uuid4()),
                parent_task_id=str(task.id),
                description=f"分析需求: {task.description[:100]}",
                priority=5,
                created_at=datetime.utcnow()
            ),
            Subtask(
                subtask_id=str(uuid4()),
                parent_task_id=str(task.id),
                description="制定执行方案",
                priority=4,
                dependencies=[],
                created_at=datetime.utcnow()
            ),
            Subtask(
                subtask_id=str(uuid4()),
                parent_task_id=str(task.id),
                description="执行主要任务",
                priority=3,
                dependencies=[],
                created_at=datetime.utcnow()
            ),
            Subtask(
                subtask_id=str(uuid4()),
                parent_task_id=str(task.id),
                description="验证和完善结果",
                priority=2,
                dependencies=[],
                created_at=datetime.utcnow()
            )
        ]
        
        return TaskDecompositionResult(
            parent_task_id=str(task.id),
            subtasks=subtasks[:max_subtasks],
            decomposition_strategy="fallback_step_by_step",
            explanation="使用简单分步策略"
        )


# ============== 子任务执行协调器 ==============

class SubtaskCoordinator:
    """
    子任务执行协调器
    
    管理子任务的调度、执行和结果聚合
    """
    
    def __init__(
        self,
        task_repo: TaskRepository,
        agent_repo: AgentRepository,
        router: IntelligentRouter
    ):
        self.task_repo = task_repo
        self.agent_repo = agent_repo
        self.router = router
        self.decomposer = TaskDecomposer()
        self._subtasks: Dict[str, Subtask] = {}
        self._parent_tasks: Dict[str, TaskDecompositionResult] = {}
        self._execution_callbacks: List[Callable] = []
    
    async def execute_cluster_task(
        self,
        task: Task,
        max_subtasks: int = 10
    ) -> Dict[str, Any]:
        """
        执行集群任务
        
        Args:
            task: 父任务
            max_subtasks: 最大子任务数
            
        Returns:
            最终结果
        """
        logger.info(
            "starting_cluster_task",
            task_id=str(task.id),
            max_subtasks=max_subtasks
        )
        
        try:
            # 1. 分解任务
            decomposition = await self.decomposer.decompose(task, max_subtasks)
            self._parent_tasks[str(task.id)] = decomposition
            
            # 2. 存储子任务
            for subtask in decomposition.subtasks:
                self._subtasks[subtask.subtask_id] = subtask
            
            # 3. 执行子任务
            results = await self._execute_subtasks(decomposition, task)
            
            # 4. 聚合结果
            final_result = await self._aggregate_results(decomposition, results)
            
            logger.info(
                "cluster_task_complete",
                task_id=str(task.id),
                subtask_count=len(decomposition.subtasks),
                success_count=sum(1 for r in results if r.get("success"))
            )
            
            return final_result
            
        except Exception as e:
            logger.error(
                "cluster_task_failed",
                task_id=str(task.id),
                error=str(e)
            )
            raise
    
    async def _execute_subtasks(
        self,
        decomposition: TaskDecompositionResult,
        parent_task: Task
    ) -> List[Dict[str, Any]]:
        """执行子任务"""
        results = []
        
        # 根据策略选择执行方式
        if decomposition.decomposition_strategy == "parallel":
            results = await self._execute_parallel(decomposition.subtasks)
        elif decomposition.decomposition_strategy == "dependency_graph":
            results = await self._execute_with_dependencies(decomposition.subtasks)
        else:
            results = await self._execute_sequential(decomposition.subtasks)
        
        return results
    
    async def _execute_sequential(self, subtasks: List[Subtask]) -> List[Dict[str, Any]]:
        """顺序执行子任务"""
        results = []
        
        for subtask in subtasks:
            result = await self._execute_single_subtask(subtask)
            results.append(result)
        
        return results
    
    async def _execute_parallel(self, subtasks: List[Subtask]) -> List[Dict[str, Any]]:
        """并行执行子任务"""
        async def execute_with_context(subtask: Subtask) -> Dict[str, Any]:
            return await self._execute_single_subtask(subtask)
        
        tasks = [execute_with_context(subtask) for subtask in subtasks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "subtask_id": subtasks[i].subtask_id,
                    "success": False,
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _execute_with_dependencies(self, subtasks: List[Subtask]) -> List[Dict[str, Any]]:
        """根据依赖关系执行子任务"""
        results = []
        executed = set()
        subtask_map = {s.subtask_id: s for s in subtasks}
        
        while len(executed) < len(subtasks):
            # 找到可执行的子任务（依赖已满足）
            executable = []
            for subtask in subtasks:
                if subtask.subtask_id not in executed:
                    deps_satisfied = all(dep in executed for dep in subtask.dependencies)
                    if deps_satisfied:
                        executable.append(subtask)
            
            if not executable:
                logger.error("no_executable_subtasks_remaining")
                break
            
            # 并行执行可执行的子任务
            batch_results = await self._execute_parallel(executable)
            results.extend(batch_results)
            
            # 标记已执行
            for subtask in executable:
                executed.add(subtask.subtask_id)
        
        return results
    
    async def _execute_single_subtask(self, subtask: Subtask) -> Dict[str, Any]:
        """执行单个子任务"""
        logger.info(
            "executing_subtask",
            subtask_id=subtask.subtask_id,
            description=subtask.description[:50]
        )
        
        # 更新状态
        subtask.status = SubtaskStatus.IN_PROGRESS
        subtask.started_at = datetime.utcnow()
        
        try:
            # 创建临时任务对象用于路由
            temp_task = Task(
                id=uuid4(),
                description=subtask.description,
                priority=subtask.priority
            )
            
            # 选择代理
            scores = await self.router.select_agent(temp_task, count=1)
            
            if not scores:
                raise Exception("No available agents")
            
            # 执行任务（模拟）
            # 在真实环境中，这里会调用代理执行
            await asyncio.sleep(0.5)
            
            result = {
                "subtask_id": subtask.subtask_id,
                "success": True,
                "result": {"output": f"执行了: {subtask.description}"},
                "agent_id": scores[0].agent_id
            }
            
            # 更新状态
            subtask.status = SubtaskStatus.COMPLETED
            subtask.completed_at = datetime.utcnow()
            subtask.result = result
            
            logger.info(
                "subtask_complete",
                subtask_id=subtask.subtask_id
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "subtask_failed",
                subtask_id=subtask.subtask_id,
                error=str(e)
            )
            
            subtask.status = SubtaskStatus.FAILED
            subtask.error = str(e)
            subtask.completed_at = datetime.utcnow()
            
            return {
                "subtask_id": subtask.subtask_id,
                "success": False,
                "error": str(e)
            }
    
    async def _aggregate_results(
        self,
        decomposition: TaskDecompositionResult,
        subtask_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """聚合子任务结果"""
        # 构建结果摘要
        summary = []
        for result in subtask_results:
            if result.get("success"):
                summary.append(f"✓ {result.get('result', {}).get('output', '完成')}")
            else:
                summary.append(f"✗ {result.get('error', '失败')}")
        
        return {
            "parent_task_id": decomposition.parent_task_id,
            "subtask_count": len(subtask_results),
            "success_count": sum(1 for r in subtask_results if r.get("success")),
            "decomposition_strategy": decomposition.decomposition_strategy,
            "subtask_results": subtask_results,
            "summary": "\n".join(summary),
            "completed_at": datetime.utcnow().isoformat()
        }
    
    def get_subtask(self, subtask_id: str) -> Optional[Subtask]:
        """获取子任务"""
        return self._subtasks.get(subtask_id)
    
    def get_parent_task_result(self, task_id: str) -> Optional[TaskDecompositionResult]:
        """获取父任务分解结果"""
        return self._parent_tasks.get(task_id)


# ============== 集群任务管理器 ==============

class ClusterTaskManager:
    """
    集群任务管理器
    
    协调多个代理完成复杂任务
    """
    
    def __init__(
        self,
        task_repo: TaskRepository,
        agent_repo: AgentRepository,
        router: IntelligentRouter
    ):
        self.task_repo = task_repo
        self.agent_repo = agent_repo
        self.router = router
        self.coordinator = SubtaskCoordinator(task_repo, agent_repo, router)
        self._active_cluster_tasks: Dict[str, asyncio.Task] = {}
    
    async def submit_cluster_task(
        self,
        task: Task,
        num_agents: int = 3,
        max_subtasks: int = 10
    ) -> str:
        """
        提交集群任务
        
        Args:
            task: 任务对象
            num_agents: 参与的代理数量
            max_subtasks: 最大子任务数
            
        Returns:
            任务ID
        """
        logger.info(
            "submitting_cluster_task",
            task_id=str(task.id),
            num_agents=num_agents,
            max_subtasks=max_subtasks
        )
        
        # 启动异步执行
        execution_task = asyncio.create_task(
            self._execute_cluster_task(
                task,
                num_agents,
                max_subtasks
            )
        )
        
        self._active_cluster_tasks[str(task.id)] = execution_task
        
        return str(task.id)
    
    async def _execute_cluster_task(
        self,
        task: Task,
        num_agents: int,
        max_subtasks: int
    ) -> None:
        """执行集群任务"""
        try:
            # 更新任务状态
            await self.task_repo.update_status(task.id, TaskStatus.IN_PROGRESS)
            
            # 执行
            result = await self.coordinator.execute_cluster_task(task, max_subtasks)
            
            # 保存结果
            await self.task_repo.set_result(task.id, result)
            await self.task_repo.update_status(task.id, TaskStatus.COMPLETED)
            
            logger.info(
                "cluster_task_finished",
                task_id=str(task.id)
            )
            
        except Exception as e:
            logger.error(
                "cluster_task_failed",
                task_id=str(task.id),
                error=str(e)
            )
            
            await self.task_repo.set_error(task.id, str(e))
            await self.task_repo.update_status(task.id, TaskStatus.FAILED)
        
        finally:
            # 清理
            if str(task.id) in self._active_cluster_tasks:
                del self._active_cluster_tasks[str(task.id)]
    
    async def get_cluster_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取集群任务状态"""
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            return {"error": "Task not found"}
        
        decomposition = self.coordinator.get_parent_task_result(task_id)
        
        return {
            "task_id": task_id,
            "status": task.status,
            "decomposition": decomposition is not None,
            "subtasks": [
                {
                    "subtask_id": s.subtask_id,
                    "description": s.description,
                    "status": s.status
                }
                for s in (decomposition.subtasks if decomposition else [])
            ]
        }
    
    async def cancel_cluster_task(self, task_id: str) -> bool:
        """取消集群任务"""
        if task_id in self._active_cluster_tasks:
            execution_task = self._active_cluster_tasks[task_id]
            execution_task.cancel()
            del self._active_cluster_tasks[task_id]
            
            # 更新状态
            await self.task_repo.update_status(task_id, TaskStatus.CANCELLED)
            
            logger.info("cluster_task_cancelled", task_id=task_id)
            return True
        
        return False


# 全局实例
coordinator_instance: Optional[SubtaskCoordinator] = None
cluster_manager_instance: Optional[ClusterTaskManager] = None


def initialize_cluster_task_management(
    task_repo: TaskRepository,
    agent_repo: AgentRepository,
    router: IntelligentRouter
) -> None:
    """初始化集群任务管理系统"""
    global coordinator_instance, cluster_manager_instance
    
    coordinator_instance = SubtaskCoordinator(task_repo, agent_repo, router)
    cluster_manager_instance = ClusterTaskManager(task_repo, agent_repo, router)
    
    logger.info("cluster_task_management_initialized")
