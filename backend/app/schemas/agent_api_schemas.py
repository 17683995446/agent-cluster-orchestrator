from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

class AgentStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"

class AgentStats(BaseModel):
    total_tasks: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_response_time: float = 0.0

class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Agent名称")
    capabilities: List[str] = Field(default_factory=list, description="能力标签列表")
    model: str = Field(default="gpt-4", description="LLM模型")
    provider: str = Field(default="openai", description="LLM提供商")

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    capabilities: Optional[List[str]] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    status: Optional[AgentStatus] = None

class AgentResponse(AgentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: AgentStatus
    current_task: Optional[str] = None
    stats: AgentStats
    created_at: datetime
    last_heartbeat: datetime

class AgentListResponse(BaseModel):
    items: List[AgentResponse]
    total: int
    page: int = 1
    page_size: int = 20

class AgentHeartbeat(BaseModel):
    agent_id: str

class CapabilityInfo(BaseModel):
    capability: str
    agent_count: int

class CapabilityStats(BaseModel):
    capabilities: List[CapabilityInfo]
    total_agents: int
