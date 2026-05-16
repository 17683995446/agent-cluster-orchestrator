from typing import List, Optional
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.agent_data_model import Agent, AgentStatus
from app.schemas.agent_api_schemas import AgentCreate, AgentUpdate
from app.repositories.agent_persistence_repository import AgentRepository
from app.core.custom_exceptions_handler import AgentNotFoundError
import structlog

logger = structlog.get_logger()

class AgentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AgentRepository(session)

    async def create(self, data: AgentCreate) -> Agent:
        agent = Agent(
            id=str(uuid.uuid4()),
            name=data.name,
            capabilities=data.capabilities,
            model=data.model,
            provider=data.provider,
            status=AgentStatus.IDLE,
            created_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        agent = await self.repo.create(agent)
        logger.info("agent_created", agent_id=agent.id, name=agent.name)
        return agent

    async def get(self, agent_id: str) -> Agent:
        agent = await self.repo.get_by_id(agent_id)
        if not agent:
            raise AgentNotFoundError(agent_id)
        return agent

    async def get_all(self, skip: int = 0, limit: int = 100) -> tuple[List[Agent], int]:
        agents = await self.repo.get_all(skip, limit)
        total = await self.repo.count_total()
        return agents, total

    async def update(self, agent_id: str, data: AgentUpdate) -> Agent:
        agent = await self.get(agent_id)
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(agent, key, value)
        
        agent = await self.repo.update(agent)
        logger.info("agent_updated", agent_id=agent.id)
        return agent

    async def delete(self, agent_id: str) -> bool:
        agent = await self.get(agent_id)
        success = await self.repo.delete(agent_id)
        if success:
            logger.info("agent_deleted", agent_id=agent_id)
        return success

    async def heartbeat(self, agent_id: str) -> bool:
        agent = await self.get(agent_id)
        success = await self.repo.update_heartbeat(agent_id)
        if success:
            logger.debug("agent_heartbeat", agent_id=agent_id)
        return success

    async def get_idle_agents(self) -> List[Agent]:
        return await self.repo.get_idle_agents()

    async def get_by_capability(self, capability: str) -> List[Agent]:
        return await self.repo.get_by_capability(capability)

    async def get_stats(self) -> dict:
        counts = await self.repo.count_by_status()
        return {
            "idle": counts.get(AgentStatus.IDLE, 0),
            "busy": counts.get(AgentStatus.BUSY, 0),
            "offline": counts.get(AgentStatus.OFFLINE, 0),
            "total": sum(counts.values())
        }

    async def get_capability_stats(self) -> dict:
        all_caps = await self.repo.get_all_capabilities()
        capabilities = []
        for cap in all_caps:
            agents = await self.repo.get_by_capability(cap)
            capabilities.append({
                "capability": cap,
                "agent_count": len(agents)
            })
        return {
            "capabilities": capabilities,
            "total_agents": await self.repo.count_total()
        }
