"""
Agent Cluster Orchestrator - Event Emitter Module

Provides convenient interface for emitting common events.
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.events.event_definitions import Event, EventType, EventPriority
from app.core.events.event_bus_core import EventBus


class EventEmitter:
    """
    Convenient event emitter wrapper for common event types.
    
    Provides named methods for frequently used event types with
    sensible defaults for priority and structure.
    """
    
    def __init__(self, event_bus: EventBus, source_identifier: str):
        self.event_bus = event_bus
        self.source_identifier = source_identifier
    
    async def emit_task_created(
        self,
        task_id: str,
        **additional_metadata
    ) -> None:
        """Emit a task creation event."""
        event = Event(
            event_type=EventType.TASK_CREATED,
            source=self.source_identifier,
            data={"task_id": task_id, **additional_metadata},
            priority=EventPriority.MEDIUM.value
        )
        await self.event_bus.publish(event)
    
    async def emit_task_updated(
        self,
        task_id: str,
        status: Optional[str] = None,
        **additional_metadata
    ) -> None:
        """Emit a task update event."""
        event = Event(
            event_type=EventType.TASK_UPDATED,
            source=self.source_identifier,
            data={"task_id": task_id, "status": status, **additional_metadata},
            priority=EventPriority.HIGH.value
        )
        await self.event_bus.publish(event)
    
    async def emit_task_completed(
        self,
        task_id: str,
        result: Any,
        **additional_metadata
    ) -> None:
        """Emit a task completion event."""
        event = Event(
            event_type=EventType.TASK_COMPLETED,
            source=self.source_identifier,
            data={"task_id": task_id, "result": result, **additional_metadata},
            priority=EventPriority.HIGH.value
        )
        await self.event_bus.publish(event)
    
    async def emit_task_failed(
        self,
        task_id: str,
        error_message: str,
        **additional_metadata
    ) -> None:
        """Emit a task failure event."""
        event = Event(
            event_type=EventType.TASK_FAILED,
            source=self.source_identifier,
            data={
                "task_id": task_id,
                "error": error_message,
                **additional_metadata
            },
            priority=EventPriority.CRITICAL.value
        )
        await self.event_bus.publish(event)
    
    async def emit_agent_status_changed(
        self,
        agent_id: str,
        new_status: str,
        **additional_metadata
    ) -> None:
        """Emit an agent status change event."""
        event = Event(
            event_type=EventType.AGENT_STATUS_CHANGED,
            source=self.source_identifier,
            data={
                "agent_id": agent_id,
                "status": new_status,
                **additional_metadata
            },
            priority=EventPriority.MEDIUM.value
        )
        await self.event_bus.publish(event)
    
    async def emit_notification(
        self,
        notification_type: str,
        notification_message: str,
        **additional_metadata
    ) -> None:
        """Emit a notification event."""
        event = Event(
            event_type=EventType.NOTIFICATION,
            source=self.source_identifier,
            data={
                "type": notification_type,
                "message": notification_message,
                **additional_metadata
            },
            priority=EventPriority.MEDIUM.value
        )
        await self.event_bus.publish(event)
    
    async def emit_metrics_updated(
        self,
        metric_name: str,
        metric_value: Any,
        **additional_metadata
    ) -> None:
        """Emit a metrics update event."""
        event = Event(
            event_type=EventType.METRICS_UPDATED,
            source=self.source_identifier,
            data={
                "metric_name": metric_name,
                "metric_value": metric_value,
                **additional_metadata
            },
            priority=EventPriority.LOW.value
        )
        await self.event_bus.publish(event)
    
    async def emit_generic_event(
        self,
        event_type: EventType,
        event_data: dict,
        priority: Optional[int] = None,
        **additional_metadata
    ) -> None:
        """
        Emit a generic event with custom type and data.
        
        Args:
            event_type: Type of event to emit
            event_data: Main data payload for the event
            priority: Optional priority level (uses MEDIUM if not specified)
            **additional_metadata: Additional metadata to attach to the event
        """
        event = Event(
            event_type=event_type,
            source=self.source_identifier,
            data={**event_data, **additional_metadata},
            priority=priority or EventPriority.MEDIUM.value
        )
        await self.event_bus.publish(event)
