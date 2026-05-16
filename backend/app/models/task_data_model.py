from sqlalchemy import String, Text, Integer, DateTime, Enum as SQLEnum, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
from enum import Enum
from app.models.agent_data_model import Base

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskType(str, Enum):
    SINGLE = "single"
    COMPOSITE = "composite"

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[TaskType] = mapped_column(
        SQLEnum(TaskType, native_enum=False),
        default=TaskType.SINGLE,
        nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, native_enum=False),
        default=TaskStatus.PENDING,
        nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)
    assigned_agent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("agents.id"), nullable=True)
    parent_task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True)
    subtask_ids: Mapped[List[str]] = mapped_column(JSON, default=list)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="tasks", lazy="selectin")

class ClusterStats:
    def __init__(self):
        self.total_agents: int = 0
        self.active_agents: int = 0
        self.idle_agents: int = 0
        self.busy_agents: int = 0
        self.offline_agents: int = 0
        self.total_tasks: int = 0
        self.pending_tasks: int = 0
        self.running_tasks: int = 0
        self.completed_tasks: int = 0
        self.failed_tasks: int = 0
        self.success_rate: float = 0.0
        self.avg_response_time: float = 0.0

    def to_dict(self):
        return {
            "total_agents": self.total_agents,
            "active_agents": self.active_agents,
            "idle_agents": self.idle_agents,
            "busy_agents": self.busy_agents,
            "offline_agents": self.offline_agents,
            "total_tasks": self.total_tasks,
            "pending_tasks": self.pending_tasks,
            "running_tasks": self.running_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": round(self.success_rate, 4),
            "avg_response_time": round(self.avg_response_time, 4)
        }
