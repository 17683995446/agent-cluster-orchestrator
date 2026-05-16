from sqlalchemy import String, Text, Integer, Float, DateTime, Enum as SQLEnum, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
from enum import Enum

class Base(DeclarativeBase):
    pass

class AgentStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"

class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    capabilities: Mapped[List[str]] = mapped_column(JSON, default=list)
    status: Mapped[AgentStatus] = mapped_column(
        SQLEnum(AgentStatus, native_enum=False),
        default=AgentStatus.IDLE,
        nullable=False
    )
    model: Mapped[str] = mapped_column(String(100), default="gpt-4")
    provider: Mapped[str] = mapped_column(String(50), default="openai")
    current_task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    total_tasks: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    total_response_time: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="agent", lazy="selectin")

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.success_count / self.total_tasks

    @property
    def avg_response_time(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.total_response_time / self.total_tasks
