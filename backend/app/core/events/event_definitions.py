"""
Agent Cluster Orchestrator - Event Definitions Module

Defines event types, data structures, and constants for the event system.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, Optional
from uuid import uuid4


class EventType(str, Enum):
    """Enumeration of all supported event types in the system."""
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


class EventPriority(Enum):
    """Enumeration of event priority levels for queue ordering."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 5
    LOW = 10


@dataclass
class Event:
    """
    Event data structure containing all necessary event information.
    
    Provides methods for serialization to JSON/dictionary format.
    """
    event_type: EventType
    source: str
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    priority: int = EventPriority.MEDIUM.value
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert event instance to serializable dictionary.
        
        Returns:
            Dictionary representation of the event
        """
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
        """
        Convert event instance to JSON string.
        
        Returns:
            JSON string representation of the event
        """
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, event_dict: Dict[str, Any]) -> "Event":
        """
        Create Event instance from dictionary.
        
        Args:
            event_dict: Dictionary containing event data
            
        Returns:
            Event instance
        """
        # Parse ISO timestamp
        if isinstance(event_dict.get("timestamp"), str):
            event_dict["timestamp"] = datetime.fromisoformat(
                event_dict["timestamp"]
            )
        
        # Parse event type
        if isinstance(event_dict.get("event_type"), str):
            event_dict["event_type"] = EventType(event_dict["event_type"])
        
        return cls(**event_dict)
