from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskType(str, Enum):
    SINGLE = "single"
    COMPOSITE = "composite"

class TaskBase(BaseModel):
    description: str = Field(..., min_length=1, description="任务描述")
    priority: int = Field(default=0, ge=0, le=10, description="优先级 0-10")
    type: TaskType = Field(default=TaskType.SINGLE, description="任务类型")

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    priority: Optional[int] = Field(None, ge=0, le=10)
    status: Optional[TaskStatus] = None

class TaskResponse(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: TaskStatus
    assigned_agent: Optional[str] = None
    subtasks: List[str] = []
    parent_task: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class TaskListResponse(BaseModel):
    items: List[TaskResponse]
    total: int
    page: int = 1
    page_size: int = 20

class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None

class ClusterExecuteRequest(BaseModel):
    description: str = Field(..., min_length=1, description="复杂任务描述")
    num_agents: int = Field(default=3, ge=2, le=10, description="Agent数量")

class ClusterExecuteResponse(BaseModel):
    parent_task_id: str
    subtask_ids: List[str]
    status: str

class TaskDecomposeRequest(BaseModel):
    description: str = Field(..., min_length=1)
    num_parts: int = Field(default=3, ge=2, le=10)
