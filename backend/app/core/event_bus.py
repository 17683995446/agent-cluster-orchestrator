"""
Phase 4: 实时数据流与事件总线
提供完整的事件驱动架构和数据流处理
"""
from __future__ import annotations

import asyncio
import json
import structlog
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Union
from uuid import uuid4

from app.core.structured_logging_config import get_structured_logger

logger = get_structured_logger(__name__)


# ============== 事件定义 ==============

class EventType(str, Enum):
    """事件类型枚举"""
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    AGENT_CREATED = "agent_created"
    AGENT_UPDATED = "agent_updated"
    AGENT_STATUS_CHANGED = "agent_status_changed"
    NOTIFICATION = "notification"
    METRICS_UPDATED = "metrics_updated"
    SYSTEM_HEALTH_CHECK = "system_health_check"
    USER_ACTION = "user_action"


@dataclass
class Event:
    """事件数据结构"""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    source: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "priority": self.priority,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """转换为JSON"""
        return json.dumps(self.to_dict())


class EventPriority(Enum):
    """事件优先级"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 5
    LOW = 10


# ============== 事件总线 ==============

class EventBus:
    """
    事件总线
    
    提供发布-订阅模式的事件传递
    """
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._all_subscribers: List[Callable] = []
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._is_running = False
        self._process_task: Optional[asyncio.Task] = None
        self._event_history: List[Event] = []
        self._max_history = 10000
    
    async def start(self) -> None:
        """启动事件总线"""
        if self._is_running:
            return
        
        self._is_running = True
        self._process_task = asyncio.create_task(self._process_events())
        logger.info("event_bus_started")
    
    async def stop(self) -> None:
        """停止事件总线"""
        self._is_running = False
        
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        
        logger.info("event_bus_stopped")
    
    def subscribe(
        self,
        callback: Callable[[Event], Any],
        event_types: Optional[List[EventType]] = None
    ) -> None:
        """
        订阅事件
        
        Args:
            callback: 事件回调函数
            event_types: 事件类型列表，None表示订阅所有
        """
        if event_types is None:
            self._all_subscribers.append(callback)
            logger.debug("subscribed_to_all_events")
        else:
            for event_type in event_types:
                if event_type not in self._subscribers:
                    self._subscribers[event_type] = []
                self._subscribers[event_type].append(callback)
                logger.debug(
                    "subscribed_to_event",
                    event_type=event_type
                )
    
    def unsubscribe(
        self,
        callback: Callable[[Event], Any],
        event_types: Optional[List[EventType]] = None
    ) -> None:
        """取消订阅"""
        if event_types is None:
            if callback in self._all_subscribers:
                self._all_subscribers.remove(callback)
        else:
            for event_type in event_types:
                if event_type in self._subscribers:
                    if callback in self._subscribers[event_type]:
                        self._subscribers[event_type].remove(callback)
    
    async def publish(self, event: Event) -> None:
        """
        发布事件
        
        Args:
            event: 事件对象
        """
        try:
            await self._event_queue.put(event)
            logger.debug(
                "event_published",
                event_id=event.event_id,
                event_type=event.event_type
            )
        except asyncio.QueueFull:
            logger.warning("event_queue_full, event_dropped")
    
    async def _process_events(self) -> None:
        """处理事件队列"""
        while self._is_running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                
                # 保存历史
                self._event_history.append(event)
                if len(self._event_history) > self._max_history:
                    self._event_history = self._event_history[-self._max_history:]
                
                # 分发事件
                await self._dispatch_event(event)
                
                self._event_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("event_processing_error", error=str(e))
    
    async def _dispatch_event(self, event: Event) -> None:
        """分发事件到订阅者"""
        # 发送到所有订阅者
        for callback in self._all_subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(
                    "subscriber_error",
                    error=str(e)
                )
        
        # 发送到类型订阅者
        if event.event_type in self._subscribers:
            for callback in self._subscribers[event.event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.error(
                        "subscriber_error",
                        error=str(e)
                    )
    
    def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 100
    ) -> List[Event]:
        """获取事件历史"""
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]


# ============== 事件发射器 ==============

class EventEmitter:
    """
    事件发射器
    
    提供便捷的事件发送接口
    """
    
    def __init__(self, bus: EventBus, source: str):
        self.bus = bus
        self.source = source
    
    async def emit_task_created(self, task_id: str, **extra) -> None:
        """发送任务创建事件"""
        event = Event(
            event_type=EventType.TASK_CREATED,
            source=self.source,
            data={"task_id": task_id, **extra},
            priority=EventPriority.MEDIUM.value
        )
        await self.bus.publish(event)
    
    async def emit_task_updated(self, task_id: str, status: Optional[str] = None, **extra) -> None:
        """发送任务更新事件"""
        event = Event(
            event_type=EventType.TASK_UPDATED,
            source=self.source,
            data={"task_id": task_id, "status": status, **extra},
            priority=EventPriority.HIGH.value
        )
        await self.bus.publish(event)
    
    async def emit_task_completed(self, task_id: str, result: Any, **extra) -> None:
        """发送任务完成事件"""
        event = Event(
            event_type=EventType.TASK_COMPLETED,
            source=self.source,
            data={"task_id": task_id, "result": result, **extra},
            priority=EventPriority.HIGH.value
        )
        await self.bus.publish(event)
    
    async def emit_task_failed(self, task_id: str, error: str, **extra) -> None:
        """发送任务失败事件"""
        event = Event(
            event_type=EventType.TASK_FAILED,
            source=self.source,
            data={"task_id": task_id, "error": error, **extra},
            priority=EventPriority.CRITICAL.value
        )
        await self.bus.publish(event)
    
    async def emit_agent_status_changed(
        self,
        agent_id: str,
        status: str,
        **extra
    ) -> None:
        """发送代理状态变更事件"""
        event = Event(
            event_type=EventType.AGENT_STATUS_CHANGED,
            source=self.source,
            data={"agent_id": agent_id, "status": status, **extra},
            priority=EventPriority.MEDIUM.value
        )
        await self.bus.publish(event)
    
    async def emit_notification(
        self,
        notification_type: str,
        message: str,
        **extra
    ) -> None:
        """发送通知事件"""
        event = Event(
            event_type=EventType.NOTIFICATION,
            source=self.source,
            data={
                "type": notification_type,
                "message": message,
                **extra
            },
            priority=EventPriority.MEDIUM.value
        )
        await self.bus.publish(event)


# ============== 数据流处理器 ==============

class StreamProcessor:
    """
    数据流处理器
    
    处理实时数据流
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._streams: Dict[str, asyncio.Queue] = {}
        self._processors: Dict[str, Callable] = {}
    
    def create_stream(self, stream_id: str, max_size: int = 1000) -> None:
        """创建数据流"""
        if stream_id not in self._streams:
            self._streams[stream_id] = asyncio.Queue(maxsize=max_size)
            logger.info("stream_created", stream_id=stream_id)
    
    def register_processor(self, stream_id: str, processor: Callable) -> None:
        """注册流处理器"""
        self._processors[stream_id] = processor
        logger.debug("processor_registered", stream_id=stream_id)
    
    async def push_to_stream(self, stream_id: str, data: Any) -> None:
        """推送到数据流"""
        if stream_id not in self._streams:
            self.create_stream(stream_id)
        
        try:
            await self._streams[stream_id].put(data)
            
            # 立即处理
            if stream_id in self._processors:
                await self._processors[stream_id](data)
                
        except asyncio.QueueFull:
            logger.warning("stream_full, data_dropped", stream_id=stream_id)
    
    async def read_from_stream(
        self,
        stream_id: str,
        timeout: float = 1.0
    ) -> Optional[Any]:
        """从数据流读取"""
        if stream_id not in self._streams:
            return None
        
        try:
            return await asyncio.wait_for(
                self._streams[stream_id].get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return None


# ============== 事件持久化器 ==============

class EventPersister:
    """
    事件持久化器
    
    将事件保存到持久化存储
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._persist_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._persist_task: Optional[asyncio.Task] = None
        self._is_running = False
        
        # 订阅所有事件
        self.event_bus.subscribe(self._on_event)
    
    async def start(self) -> None:
        """启动持久化器"""
        if self._is_running:
            return
        
        self._is_running = True
        self._persist_task = asyncio.create_task(self._process_persist_queue())
        logger.info("event_persister_started")
    
    async def stop(self) -> None:
        """停止持久化器"""
        self._is_running = False
        
        if self._persist_task:
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass
        
        logger.info("event_persister_stopped")
    
    async def _on_event(self, event: Event) -> None:
        """事件回调"""
        try:
            await self._persist_queue.put(event)
        except asyncio.QueueFull:
            logger.warning("persist_queue_full, event_dropped")
    
    async def _process_persist_queue(self) -> None:
        """处理持久化队列"""
        while self._is_running:
            try:
                event = await asyncio.wait_for(
                    self._persist_queue.get(),
                    timeout=1.0
                )
                
                # 这里应该实际保存到数据库
                # 暂时只记录日志
                logger.debug(
                    "event_would_be_persisted",
                    event_id=event.event_id
                )
                
                self._persist_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("event_persist_error", error=str(e))


# ============== 全局实例 ==============

event_bus_instance: Optional[EventBus] = None
stream_processor_instance: Optional[StreamProcessor] = None
event_persister_instance: Optional[EventPersister] = None


def initialize_event_system() -> None:
    """初始化事件系统"""
    global event_bus_instance, stream_processor_instance, event_persister_instance
    
    event_bus_instance = EventBus()
    stream_processor_instance = StreamProcessor(event_bus_instance)
    event_persister_instance = EventPersister(event_bus_instance)
    
    logger.info("event_system_initialized")


async def start_event_system() -> None:
    """启动事件系统"""
    if not event_bus_instance:
        initialize_event_system()
    
    await event_bus_instance.start()
    await event_persister_instance.start()


async def stop_event_system() -> None:
    """停止事件系统"""
    if event_persister_instance:
        await event_persister_instance.stop()
    if event_bus_instance:
        await event_bus_instance.stop()


def get_event_bus() -> EventBus:
    """获取事件总线"""
    if not event_bus_instance:
        initialize_event_system()
    return event_bus_instance


def get_event_emitter(source: str) -> EventEmitter:
    """获取事件发射器"""
    return EventEmitter(get_event_bus(), source)
