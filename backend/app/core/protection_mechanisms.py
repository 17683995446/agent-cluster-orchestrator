"""
Agent Cluster Orchestrator - 熔断器与系统保护机制

实现完整的熔断器、超时保护、连接池等核心保护机制
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic
from uuid import uuid4
import structlog

logger = structlog.get_logger(__name__)


# ============== 熔断器状态和配置 ==============

class CircuitState(str, Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常，允许请求通过
    OPEN = "open"          # 打开，拒绝所有请求
    HALF_OPEN = "half_open"  # 半开，允许部分请求通过


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_duration: float = 60.0
    half_open_max_calls: int = 3
    failure_rate_threshold: float = 0.5
    min_call_count: int = 10


# ============== 熔断器核心实现 ==============

class CircuitBreakerError(Exception):
    """熔断器异常"""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """熔断器打开异常"""
    pass


class CircuitBreaker:
    """
    完整的熔断器实现
    
    特性：
    - 三态状态机：CLOSED, OPEN, HALF_OPEN
    - 自动恢复
    - 统计失败率和成功率
    - 可配置阈值
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.on_state_change = on_state_change
        
        # 状态
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.total_calls = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        
        # 统计
        self.call_history: List[Dict[str, Any]] = []
        self.state_changes: List[Dict[str, Any]] = []
        
        logger.info(f"circuit_breaker_initialized", name=name, config=self.config)
    
    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN
    
    async def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        通过熔断器执行函数
        
        Args:
            func: 要执行的异步函数
            *args: 函数参数
            fallback: 熔断时的降级函数
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            CircuitBreakerOpenError: 熔断器打开时抛出
        """
        # 检查熔断器状态
        if not self._allow_request():
            logger.warning(
                "circuit_breaker_rejected",
                name=self.name,
                state=self.state
            )
            
            if fallback:
                return await fallback(*args, **kwargs)
            
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN"
            )
        
        # 执行函数
        start_time = time.time()
        self.total_calls += 1
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # 成功
            await self._on_success(time.time() - start_time)
            return result
            
        except Exception as e:
            # 失败
            await self._on_failure(time.time() - start_time, str(e))
            raise
    
    def _allow_request(self) -> bool:
        """检查是否允许请求"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # 检查是否应该尝试恢复
            if self._should_attempt_reset():
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            # 半开状态限制请求数
            if self.half_open_calls < self.config.half_open_max_calls:
                self.half_open_calls += 1
                return True
            return False
        
        return False
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试恢复"""
        if self.last_failure_time is None:
            return True
        
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.config.timeout_duration
    
    async def _on_success(self, duration: float):
        """处理成功调用"""
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.config.success_threshold:
                logger.info(
                    "circuit_breaker_recovered",
                    name=self.name,
                    half_open_successes=self.success_count
                )
                self._transition_to(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            # 重置信任
            pass
        
        # 记录
        self._record_call(success=True, duration=duration)
    
    async def _on_failure(self, duration: float, error: str):
        """处理失败调用"""
        self.failure_count += 1
        self.success_count = 0
        self.last_failure_time = time.time()
        
        # 记录
        self._record_call(success=False, duration=duration, error=error)
        
        if self.state == CircuitState.HALF_OPEN:
            # 半开状态下任何失败都重新打开
            logger.warning(
                "circuit_breaker_reopened",
                name=self.name,
                half_open_calls=self.half_open_calls
            )
            self._transition_to(CircuitState.OPEN)
            
        elif self.state == CircuitState.CLOSED:
            # 检查是否应该打开
            if self.failure_count >= self.config.failure_threshold:
                logger.error(
                    "circuit_breaker_opened",
                    name=self.name,
                    failure_count=self.failure_count
                )
                self._transition_to(CircuitState.OPEN)
    
    def _transition_to(self, new_state: CircuitState):
        """状态转换"""
        old_state = self.state
        self.state = new_state
        
        # 重置计数器
        if new_state == CircuitState.HALF_OPEN:
            self.half_open_calls = 0
            self.success_count = 0
        elif new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
        
        # 记录状态变化
        self.state_changes.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # 触发回调
        if self.on_state_change:
            try:
                self.on_state_change(old_state, new_state)
            except Exception as e:
                logger.error(f"state_change_callback_error: {e}")
        
        logger.info(
            "circuit_breaker_state_changed",
            name=self.name,
            from_state=old_state.value,
            to_state=new_state.value
        )
    
    def _record_call(self, success: bool, duration: float, error: Optional[str] = None):
        """记录调用"""
        self.call_history.append({
            "success": success,
            "duration": duration,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": self.state.value
        })
        
        # 保持最近1000条记录
        if len(self.call_history) > 1000:
            self.call_history = self.call_history[-1000:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取熔断器统计"""
        recent_calls = self.call_history[-self.config.min_call_count:]
        
        if not recent_calls:
            return {
                "name": self.name,
                "state": self.state.value,
                "total_calls": self.total_calls,
                "failure_count": self.failure_count,
                "success_count": self.success_count
            }
        
        recent_success = sum(1 for c in recent_calls if c["success"])
        recent_failure = len(recent_calls) - recent_success
        failure_rate = recent_failure / len(recent_calls)
        
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "recent_calls": len(recent_calls),
            "recent_success": recent_success,
            "recent_failure": recent_failure,
            "recent_failure_rate": failure_rate,
            "last_failure_time": self.last_failure_time,
            "state_changes": len(self.state_changes)
        }
    
    def reset(self):
        """重置熔断器"""
        self._transition_to(CircuitState.CLOSED)
        self.call_history.clear()
        self.state_changes.clear()
        logger.info("circuit_breaker_reset", name=self.name)


# ============== 熔断器管理器 ==============

class CircuitBreakerManager:
    """
    熔断器管理器
    
    管理和监控多个熔断器
    """
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
        logger.info("circuit_breaker_manager_initialized")
    
    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name, config)
        
        return self.breakers[name]
    
    async def call(
        self,
        breaker_name: str,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """通过指定熔断器执行函数"""
        breaker = self.get_or_create(breaker_name)
        return await breaker.call(func, *args, fallback=fallback, **kwargs)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有熔断器统计"""
        return {
            name: breaker.get_stats()
            for name, breaker in self.breakers.items()
        }
    
    def reset_all(self):
        """重置所有熔断器"""
        for breaker in self.breakers.values():
            breaker.reset()


# ============== 超时保护 ==============

@dataclass
class TimeoutConfig:
    """超时配置"""
    default_timeout: float = 5.0
    max_timeout: float = 30.0
    enable_timeout_protection: bool = True


class TimeoutError(Exception):
    """超时异常"""
    pass


async def execute_with_timeout(
    coro,
    timeout: float,
    task_name: Optional[str] = None
) -> Any:
    """
    带超时的执行
    
    Args:
        coro: 协程或可调用对象
        timeout: 超时时间（秒）
        task_name: 任务名称（用于日志）
        
    Returns:
        执行结果
        
    Raises:
        TimeoutError: 执行超时
    """
    task_name = task_name or "anonymous"
    
    try:
        result = await asyncio.wait_for(
            coro if asyncio.iscoroutine(coro) else coro(),
            timeout=timeout
        )
        return result
        
    except asyncio.TimeoutError:
        logger.warning(
            "task_timeout",
            task_name=task_name,
            timeout=timeout
        )
        raise TimeoutError(
            f"Task '{task_name}' exceeded timeout of {timeout}s"
        )


class TimeoutMonitor:
    """
    超时监控器
    
    监控所有超时事件并提供统计
    """
    
    def __init__(self):
        self.timeouts: List[Dict[str, Any]] = []
        self.callbacks: List[Callable] = []
        self.config = TimeoutConfig()
        logger.info("timeout_monitor_initialized")
    
    def register_callback(self, callback: Callable[[str, float], None]):
        """注册超时回调"""
        self.callbacks.append(callback)
    
    def on_timeout(self, task_id: str, timeout: float):
        """触发超时事件"""
        event = {
            "task_id": task_id,
            "timeout": timeout,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.timeouts.append(event)
        
        # 保持最近100条记录
        if len(self.timeouts) > 100:
            self.timeouts = self.timeouts[-100:]
        
        # 触发回调
        for callback in self.callbacks:
            try:
                callback(task_id, timeout)
            except Exception as e:
                logger.error(f"timeout_callback_error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取超时统计"""
        if not self.timeouts:
            return {
                "total_timeouts": 0,
                "recent_timeouts": 0
            }
        
        recent = self.timeouts[-10:]
        
        return {
            "total_timeouts": len(self.timeouts),
            "recent_timeouts": len(recent),
            "avg_timeout": sum(e["timeout"] for e in recent) / len(recent) if recent else 0,
            "last_timeout": self.timeouts[-1] if self.timeouts else None
        }


# ============== 连接池管理 ==============

@dataclass
class PoolConfig:
    """连接池配置"""
    min_size: int = 5
    max_size: int = 100
    max_idle_time: float = 300.0
    acquire_timeout: float = 10.0
    health_check_interval: float = 60.0


class PoolExhaustedError(Exception):
    """连接池耗尽异常"""
    pass


class ConnectionWrapper:
    """连接包装器"""
    
    def __init__(self, connection: Any, pool: 'ConnectionPool'):
        self.connection = connection
        self.pool = pool
        self.created_at = time.time()
        self.last_used_at = time.time()
        self.in_use = False
    
    async def __aenter__(self):
        self.in_use = True
        self.last_used_at = time.time()
        return self.connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.in_use = False
        await self.pool.release(self)


T = TypeVar('T')


class ConnectionPool:
    """
    连接池
    
    管理数据库或网络连接的复用
    """
    
    def __init__(self, config: PoolConfig, factory: Callable):
        self.config = config
        self.factory = factory
        self.available: List[ConnectionWrapper] = []
        self.acquired: Set[ConnectionWrapper] = set()
        self._lock = asyncio.Lock()
        self._closed = False
        logger.info("connection_pool_initialized", config=config)
    
    async def initialize(self):
        """初始化连接池"""
        async with self._lock:
            for _ in range(self.config.min_size):
                conn = await self.factory()
                wrapper = ConnectionWrapper(conn, self)
                self.available.append(wrapper)
        
        logger.info("connection_pool_initialized_connections", count=len(self.available))
    
    async def acquire(self) -> ConnectionWrapper:
        """获取连接"""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        async with self._lock:
            # 尝试从可用连接中获取
            while self.available:
                wrapper = self.available.pop(0)
                
                # 检查连接是否健康
                if await self._is_healthy(wrapper):
                    self.acquired.add(wrapper)
                    return wrapper
                else:
                    # 连接不健康，关闭它
                    await self._close_connection(wrapper)
            
            # 检查是否可以达到最大连接数
            total = len(self.available) + len(self.acquired)
            if total >= self.config.max_size:
                # 等待可用连接
                try:
                    await asyncio.wait_for(
                        self._wait_for_available(),
                        timeout=self.config.acquire_timeout
                    )
                except asyncio.TimeoutError:
                    raise PoolExhaustedError(
                        f"Connection pool exhausted, max_size={self.config.max_size}"
                    )
            else:
                # 创建新连接
                conn = await self.factory()
                wrapper = ConnectionWrapper(conn, self)
                self.acquired.add(wrapper)
                return wrapper
        
        # 递归获取（处理竞争情况）
        return await self.acquire()
    
    async def _wait_for_available(self):
        """等待可用连接"""
        while not self.available:
            await asyncio.sleep(0.1)
    
    async def release(self, wrapper: ConnectionWrapper):
        """释放连接"""
        if wrapper not in self.acquired:
            return
        
        async with self._lock:
            self.acquired.discard(wrapper)
            
            # 检查连接是否应该关闭
            if await self._should_close(wrapper):
                await self._close_connection(wrapper)
            else:
                wrapper.in_use = False
                self.available.append(wrapper)
    
    async def _is_healthy(self, wrapper: ConnectionWrapper) -> bool:
        """检查连接是否健康"""
        # 检查空闲时间
        idle_time = time.time() - wrapper.last_used_at
        if idle_time > self.config.max_idle_time:
            return False
        
        # 检查连接是否有效（实际实现可能需要ping）
        # 这里简化检查
        return True
    
    async def _should_close(self, wrapper: ConnectionWrapper) -> bool:
        """检查连接是否应该关闭"""
        idle_time = time.time() - wrapper.last_used_at
        total = len(self.available) + len(self.acquired)
        
        # 超过最小连接数且空闲太久
        if total > self.config.min_size and idle_time > self.config.max_idle_time:
            return True
        
        return False
    
    async def _close_connection(self, wrapper: ConnectionWrapper):
        """关闭连接"""
        try:
            if hasattr(wrapper.connection, 'close'):
                wrapper.connection.close()
        except Exception as e:
            logger.warning(f"error_closing_connection: {e}")
    
    async def close(self):
        """关闭连接池"""
        self._closed = True
        
        async with self._lock:
            # 关闭所有连接
            for wrapper in self.available + list(self.acquired):
                await self._close_connection(wrapper)
            
            self.available.clear()
            self.acquired.clear()
        
        logger.info("connection_pool_closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计"""
        return {
            "available": len(self.available),
            "acquired": len(self.acquired),
            "total": len(self.available) + len(self.acquired),
            "max_size": self.config.max_size,
            "utilization": (len(self.acquired) / self.config.max_size * 100) if self.config.max_size > 0 else 0
        }


# ============== 自适应队列 ==============

@dataclass
class QueueConfig:
    """队列配置"""
    initial_capacity: int = 100
    max_capacity: int = 1000
    growth_factor: float = 1.5
    shrink_factor: float = 0.5


class QueueFullError(Exception):
    """队列满异常"""
    pass


class PriorityItem:
    """优先级项"""
    
    def __init__(self, priority: int, item: Any):
        self.priority = priority
        self.item = item
        self.created_at = time.time()
    
    def __lt__(self, other: 'PriorityItem'):
        # 优先级高的排在前面（最大堆）
        return self.priority > other.priority


class AdaptiveQueue:
    """
    自适应队列
    
    特性：
    - 自动扩容和缩容
    - 优先级支持
    - 背压控制
    """
    
    def __init__(self, config: Optional[QueueConfig] = None):
        self.config = config or QueueConfig()
        self.capacity = self.config.initial_capacity
        self.queue: List[PriorityItem] = []
        self.stats = {
            "enqueued": 0,
            "dequeued": 0,
            "rejected": 0,
            "growth_count": 0,
            "shrink_count": 0
        }
        self._lock = asyncio.Lock()
        logger.info("adaptive_queue_initialized", config=self.config)
    
    async def enqueue(
        self,
        item: Any,
        priority: int = 0
    ) -> bool:
        """
        入队
        
        Args:
            item: 要入队的项
            priority: 优先级（越高越先出队）
            
        Returns:
            是否入队成功
            
        Raises:
            QueueFullError: 队列已满且无法扩容
        """
        async with self._lock:
            # 检查容量
            if len(self.queue) >= self.capacity:
                # 尝试扩容
                if self.capacity < self.config.max_capacity:
                    old_capacity = self.capacity
                    self.capacity = min(
                        int(self.capacity * self.config.growth_factor),
                        self.config.max_capacity
                    )
                    self.stats["growth_count"] += 1
                    logger.info(
                        "queue_grew",
                        old_capacity=old_capacity,
                        new_capacity=self.capacity
                    )
                else:
                    # 无法扩容，尝试移除最低优先级
                    if self.queue:
                        lowest = self.queue[-1]
                        if lowest.priority < priority:
                            # 新项优先级更高，移除最低优先级
                            self.queue.pop()
                            self.stats["rejected"] += 1
                        else:
                            # 新项优先级更低，拒绝
                            self.stats["rejected"] += 1
                            return False
                    else:
                        self.stats["rejected"] += 1
                        return False
            
            # 入队
            priority_item = PriorityItem(priority, item)
            self.queue.append(priority_item)
            self.queue.sort()  # 保持优先级顺序
            self.stats["enqueued"] += 1
            
            return True
    
    async def dequeue(self) -> Optional[Any]:
        """出队"""
        async with self._lock:
            if not self.queue:
                return None
            
            item = self.queue.pop(0)
            self.stats["dequeued"] += 1
            
            # 检查是否应该缩容
            if (len(self.queue) < self.capacity * self.config.shrink_factor
                and self.capacity > self.config.initial_capacity):
                old_capacity = self.capacity
                self.capacity = max(
                    int(self.capacity * self.config.shrink_factor),
                    self.config.initial_capacity
                )
                self.stats["shrink_count"] += 1
                logger.info(
                    "queue_shrank",
                    old_capacity=old_capacity,
                    new_capacity=self.capacity
                )
            
            return item.item
    
    def get_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        return {
            **self.stats,
            "current_size": len(self.queue),
            "capacity": self.capacity,
            "utilization": len(self.queue) / self.capacity * 100 if self.capacity > 0 else 0
        }


# ============== 全局实例 ==============

_circuit_breaker_manager: Optional[CircuitBreakerManager] = None
_timeout_monitor: Optional[TimeoutMonitor] = None


def initialize_protection_system() -> None:
    """初始化保护系统"""
    global _circuit_breaker_manager, _timeout_monitor
    
    _circuit_breaker_manager = CircuitBreakerManager()
    _timeout_monitor = TimeoutMonitor()
    
    logger.info("protection_system_initialized")


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """获取熔断器管理器"""
    if not _circuit_breaker_manager:
        initialize_protection_system()
    return _circuit_breaker_manager


def get_timeout_monitor() -> TimeoutMonitor:
    """获取超时监控器"""
    if not _timeout_monitor:
        initialize_protection_system()
    return _timeout_monitor
