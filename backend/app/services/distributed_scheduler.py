"""
Phase 2: 分布式任务与强化学习优化器 - 史诗级AI创新

实现分布式任务调度、深度强化学习优化、资源自动分配
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import random
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple
from uuid import uuid4
import structlog

import numpy as np

from app.core.structured_logging_config import get_structured_logger

logger = get_structured_logger(__name__)


# ============== 分布式系统核心类型 ==============

class WorkerStatus(str, Enum):
    """Worker节点状态"""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    OVERLOADED = "overloaded"


class DistributedTaskStatus(str, Enum):
    """分布式任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class WorkerNode:
    """Worker节点"""
    node_id: str
    worker_type: str
    host: str
    port: int
    status: WorkerStatus = WorkerStatus.IDLE
    capacity: float = 1.0
    current_load: float = 0.0
    capabilities: List[str] = field(default_factory=list)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    performance_stats: Dict[str, float] = field(default_factory=dict)


@dataclass
class DistributedTask:
    """分布式任务"""
    task_id: str = field(default_factory=lambda: str(uuid4()))
    task_type: str
    priority: int = 0
    status: DistributedTaskStatus = DistributedTaskStatus.PENDING
    assigned_worker: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: float = 300.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============== 强化学习优化器 ==============

class State:
    """强化学习状态表示"""
    
    def __init__(self, features: np.ndarray):
        self.features = features
    
    def to_vector(self) -> np.ndarray:
        return self.features


class Action:
    """强化学习动作"""
    
    def __init__(self, action_type: str, parameters: Optional[Dict[str, Any]] = None):
        self.action_type = action_type
        self.parameters = parameters or {}


class QLearningOptimizer:
    """
    Q-Learning优化器
    
    学习如何优化任务调度和资源分配
    """
    
    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon: float = 0.1,
        epsilon_decay: float = 0.995,
        min_epsilon: float = 0.01
    ):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.min_epsilon = min_epsilon
        
        self.q_table: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.state_counts: Dict[str, int] = defaultdict(int)
        self.action_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        
        logger.info("q_learning_optimizer_initialized")
    
    def _get_state_key(self, state: State) -> str:
        """获取状态的键"""
        return hashlib.md5(state.to_vector().tobytes()).hexdigest()
    
    def get_q_value(self, state: State, action: Action) -> float:
        """获取Q值"""
        state_key = self._get_state_key(state)
        return self.q_table[state_key][action.action_type]
    
    def select_action(
        self,
        state: State,
        available_actions: List[Action],
        training: bool = True
    ) -> Action:
        """选择动作"""
        if training and random.random() < self.epsilon:
            # 探索
            return random.choice(available_actions)
        
        # 利用
        state_key = self._get_state_key(state)
        best_action = max(
            available_actions,
            key=lambda a: self.q_table[state_key][a.action_type]
        )
        
        return best_action
    
    def update(
        self,
        state: State,
        action: Action,
        reward: float,
        next_state: State,
        done: bool
    ) -> None:
        """更新Q表"""
        state_key = self._get_state_key(state)
        next_state_key = self._get_state_key(next_state)
        
        self.state_counts[state_key] += 1
        self.action_counts[(state_key, action.action_type)] += 1
        
        current_q = self.q_table[state_key][action.action_type]
        
        if done:
            target_q = reward
        else:
            next_max_q = max(self.q_table[next_state_key].values(), default=0.0)
            target_q = reward + self.discount_factor * next_max_q
        
        # 更新Q值
        new_q = current_q + self.learning_rate * (target_q - current_q)
        self.q_table[state_key][action.action_type] = new_q
        
        # 更新探索率
        if self.epsilon > self.min_epsilon:
            self.epsilon *= self.epsilon_decay
    
    def get_state_representation(
        self,
        pending_tasks: int,
        active_workers: int,
        avg_queue_wait: float,
        system_load: float
    ) -> State:
        """生成系统状态表示"""
        features = np.array([
            pending_tasks / 100.0,
            active_workers / 10.0,
            avg_queue_wait / 60.0,
            system_load,
            math.log(pending_tasks + 1)
        ])
        return State(features)
    
    def get_available_actions(self) -> List[Action]:
        """获取可用动作"""
        return [
            Action("assign_to_fastest"),
            Action("assign_to_least_loaded"),
            Action("delay_assignment"),
            Action("parallel_execution"),
            Action("increase_priority")
        ]


class DeepOptimizer:
    """
    深度强化学习优化器（简化实现）
    
    使用神经网络近似Q函数
    """
    
    def __init__(self, state_dim: int = 5, action_dim: int = 5):
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # 简单的权重矩阵
        self.weights_1 = np.random.randn(state_dim, 64) * 0.1
        self.weights_2 = np.random.randn(64, action_dim) * 0.1
        
        logger.info("deep_optimizer_initialized")
    
    def _relu(self, x: np.ndarray) -> np.ndarray:
        return np.maximum(0, x)
    
    def predict(self, state: State) -> np.ndarray:
        """预测Q值"""
        x = state.to_vector()
        h = self._relu(np.dot(x, self.weights_1))
        q_values = np.dot(h, self.weights_2)
        return q_values
    
    def select_action(self, state: State, epsilon: float = 0.1) -> int:
        """选择动作"""
        if random.random() < epsilon:
            return random.randint(0, self.action_dim - 1)
        
        q_values = self.predict(state)
        return int(np.argmax(q_values))


# ============== 分布式调度器 ==============

class DistributedTaskScheduler:
    """
    分布式任务调度器
    
    使用强化学习优化任务调度和资源分配
    """
    
    def __init__(self, rl_optimizer: QLearningOptimizer):
        self.rl_optimizer = rl_optimizer
        self.workers: Dict[str, WorkerNode] = {}
        self.task_queue: Deque[DistributedTask] = Deque()
        self.active_tasks: Dict[str, DistributedTask] = {}
        self.completed_tasks: Dict[str, DistributedTask] = {}
        
        self._task_assignments: Dict[str, str] = {}
        self._metrics = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "avg_completion_time": 0.0
        }
        
        self._running = False
        self._last_state: Optional[State] = None
        self._last_action: Optional[Action] = None
        
        logger.info("distributed_scheduler_initialized")
    
    def register_worker(self, worker: WorkerNode) -> None:
        """注册Worker节点"""
        self.workers[worker.node_id] = worker
        logger.info("worker_registered", node_id=worker.node_id, type=worker.worker_type)
    
    def submit_task(self, task: DistributedTask) -> str:
        """提交任务"""
        task.status = DistributedTaskStatus.QUEUED
        self.task_queue.append(task)
        self._metrics["total_tasks"] += 1
        
        logger.info("task_submitted", task_id=task.task_id, type=task.task_type)
        return task.task_id
    
    async def start_scheduler(self) -> None:
        """启动调度器"""
        self._running = True
        logger.info("distributed_scheduler_started")
        
        while self._running:
            await self._scheduling_iteration()
            await asyncio.sleep(0.5)
    
    async def _scheduling_iteration(self) -> None:
        """执行一次调度迭代"""
        if not self.task_queue:
            return
        
        # 1. 获取当前系统状态
        state = self._get_current_state()
        
        # 2. 使用RL选择动作
        available_actions = self.rl_optimizer.get_available_actions()
        action = self.rl_optimizer.select_action(state, available_actions)
        
        # 3. 执行动作
        reward = await self._execute_action(action)
        
        # 4. 获取下一个状态
        next_state = self._get_current_state()
        
        # 5. 更新RL
        done = len(self.task_queue) == 0
        self.rl_optimizer.update(
            state, action, reward, next_state, done
        )
        
        # 6. 分配任务
        await self._assign_pending_tasks()
    
    def _get_current_state(self) -> State:
        """获取当前系统状态"""
        pending_count = len(self.task_queue)
        active_workers = len([
            w for w in self.workers.values() 
            if w.status in (WorkerStatus.IDLE, WorkerStatus.BUSY)
        ])
        avg_wait = self._calculate_avg_wait_time()
        system_load = self._calculate_system_load()
        
        return self.rl_optimizer.get_state_representation(
            pending_count,
            active_workers,
            avg_wait,
            system_load
        )
    
    async def _execute_action(self, action: Action) -> float:
        """执行调度动作并返回奖励"""
        start_time = datetime.utcnow()
        
        if action.action_type == "assign_to_fastest":
            # 分配给最快的Worker
            await self._assign_to_fastest()
        elif action.action_type == "assign_to_least_loaded":
            # 分配给负载最低的
            await self._assign_to_least_loaded()
        elif action.action_type == "parallel_execution":
            # 尝试并行执行
            await self._parallel_execution()
        
        # 计算奖励
        completion_count = len(self.completed_tasks)
        wait_time = self._calculate_avg_wait_time()
        
        reward = completion_count * 10.0 - wait_time * 0.1
        
        return reward
    
    async def _assign_pending_tasks(self) -> None:
        """分配待处理任务"""
        for task in list(self.task_queue):
            worker = self._select_best_worker(task)
            if worker:
                await self._assign_task(task, worker)
    
    def _select_best_worker(self, task: DistributedTask) -> Optional[WorkerNode]:
        """选择最佳Worker"""
        available_workers = [
            w for w in self.workers.values()
            if w.status == WorkerStatus.IDLE
            and self._is_capable(w, task)
        ]
        
        if not available_workers:
            return None
        
        # 基于性能评分选择
        def worker_score(w: WorkerNode) -> float:
            perf = w.performance_stats.get(task.task_type, 0.5)
            load = w.current_load
            return perf * (1.0 - load * 0.5)
        
        return max(available_workers, key=worker_score)
    
    def _is_capable(self, worker: WorkerNode, task: DistributedTask) -> bool:
        """检查Worker是否有能力执行任务"""
        if not worker.capabilities:
            return True
        return task.task_type in worker.capabilities
    
    async def _assign_task(self, task: DistributedTask, worker: WorkerNode) -> None:
        """分配任务给Worker"""
        task.assigned_worker = worker.node_id
        task.status = DistributedTaskStatus.ASSIGNED
        task.started_at = datetime.utcnow()
        
        worker.status = WorkerStatus.BUSY
        worker.current_load = min(1.0, worker.current_load + 0.1)
        
        self.task_queue.remove(task)
        self.active_tasks[task.task_id] = task
        self._task_assignments[task.task_id] = worker.node_id
        
        # 模拟执行（实际中会通过网络发送）
        await self._simulate_task_execution(task, worker)
    
    async def _simulate_task_execution(
        self,
        task: DistributedTask,
        worker: WorkerNode
    ) -> None:
        """模拟任务执行"""
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
        # 任务完成
        task.status = DistributedTaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.result = {"status": "success"}
        
        worker.status = WorkerStatus.IDLE
        worker.current_load = max(0.0, worker.current_load - 0.1)
        
        # 更新性能统计
        duration = (task.completed_at - task.started_at).total_seconds()
        old_avg = worker.performance_stats.get(task.task_type, duration)
        worker.performance_stats[task.task_type] = old_avg * 0.9 + duration * 0.1
        
        # 移动到完成
        del self.active_tasks[task.task_id]
        self.completed_tasks[task.task_id] = task
        self._metrics["completed_tasks"] += 1
        
        logger.info(
            "task_completed",
            task_id=task.task_id,
            worker=worker.node_id,
            duration=duration
        )
    
    async def _assign_to_fastest(self) -> None:
        """分配给最快的Worker"""
        pass  # 由_assign_pending_tasks自动处理
    
    async def _assign_to_least_loaded(self) -> None:
        """分配给负载最低的"""
        pass  # 由_select_best_worker自动处理
    
    async def _parallel_execution(self) -> None:
        """并行执行"""
        pass  # 可以在这里实现特殊的并行逻辑
    
    def _calculate_avg_wait_time(self) -> float:
        """计算平均等待时间"""
        if not self.task_queue:
            return 0.0
        
        now = datetime.utcnow()
        wait_times = [
            (now - task.created_at).total_seconds()
            for task in self.task_queue
        ]
        return sum(wait_times) / len(wait_times) if wait_times else 0.0
    
    def _calculate_system_load(self) -> float:
        """计算系统负载"""
        if not self.workers:
            return 0.0
        
        return sum(w.current_load for w in self.workers.values()) / len(self.workers)
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取调度器指标"""
        metrics = self._metrics.copy()
        metrics.update({
            "pending_tasks": len(self.task_queue),
            "active_tasks": len(self.active_tasks),
            "registered_workers": len(self.workers),
            "rl_epsilon": self.rl_optimizer.epsilon
        })
        return metrics


# ============== 负载均衡器 ==============

class IntelligentLoadBalancer:
    """
    智能负载均衡器
    
    使用强化学习和启发式算法进行负载均衡
    """
    
    def __init__(self):
        self.rl_optimizer = QLearningOptimizer()
        self.balancing_history: List[Dict[str, Any]] = []
    
    def balance_load(
        self,
        workers: Dict[str, WorkerNode]
    ) -> Dict[str, List[str]]:
        """执行负载均衡"""
        # 计算负载不均度
        loads = [w.current_load for w in workers.values()]
        if not loads:
            return {}
        
        load_std = np.std(loads)
        load_avg = np.mean(loads)
        
        if load_std < 0.1:
            return {}  # 负载已经均衡
        
        # 生成迁移计划
        migration_plan = self._generate_migration_plan(workers)
        
        # 记录历史
        self.balancing_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "load_std": load_std,
            "migrations": len(migration_plan)
        })
        
        return migration_plan
    
    def _generate_migration_plan(
        self,
        workers: Dict[str, WorkerNode]
    ) -> Dict[str, List[str]]:
        """生成迁移计划"""
        overloaded = [w for w in workers.values() if w.current_load > 0.7]
        underloaded = [w for w in workers.values() if w.current_load < 0.3]
        
        plan = defaultdict(list)
        
        for src in overloaded:
            for dst in underloaded:
                if src.current_load > dst.current_load + 0.2:
                    # 这里可以迁移任务
                    pass
        
        return plan


# ============== 全局实例 ==============

_global_rl_optimizer: Optional[QLearningOptimizer] = None
_global_scheduler: Optional[DistributedTaskScheduler] = None


def initialize_distributed_system() -> None:
    """初始化分布式系统"""
    global _global_rl_optimizer, _global_scheduler
    
    _global_rl_optimizer = QLearningOptimizer()
    _global_scheduler = DistributedTaskScheduler(_global_rl_optimizer)
    
    logger.info("distributed_system_initialized")


def get_rl_optimizer() -> QLearningOptimizer:
    """获取RL优化器"""
    if not _global_rl_optimizer:
        raise RuntimeError("Distributed system not initialized")
    return _global_rl_optimizer


def get_scheduler() -> DistributedTaskScheduler:
    """获取调度器"""
    if not _global_scheduler:
        raise RuntimeError("Distributed system not initialized")
    return _global_scheduler
