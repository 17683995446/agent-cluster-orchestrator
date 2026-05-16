from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.models.agent_data_model import Agent, AgentStatus

class AgentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, agent: Agent) -> Agent:
        self.session.add(agent)
        await self.session.flush()
        await self.session.refresh(agent)
        return agent

    async def get_by_id(self, agent_id: str) -> Optional[Agent]:
        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Agent]:
        result = await self.session.execute(
            select(Agent).offset(skip).limit(limit).order_by(Agent.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_status(self, status: AgentStatus) -> List[Agent]:
        result = await self.session.execute(
            select(Agent).where(Agent.status == status)
        )
        return list(result.scalars().all())

    async def get_idle_agents(self) -> List[Agent]:
        return await self.get_by_status(AgentStatus.IDLE)

    async def get_by_capability(self, capability: str) -> List[Agent]:
        result = await self.session.execute(
            select(Agent).where(Agent.capabilities.contains([capability]))
        )
        return list(result.scalars().all())

    async def update(self, agent: Agent) -> Agent:
        await self.session.flush()
        await self.session.refresh(agent)
        return agent

    async def delete(self, agent_id: str) -> bool:
        result = await self.session.execute(
            delete(Agent).where(Agent.id == agent_id)
        )
        return result.rowcount > 0

    async def update_heartbeat(self, agent_id: str) -> bool:
        from datetime import datetime
        result = await self.session.execute(
            update(Agent)
            .where(Agent.id == agent_id)
            .values(last_heartbeat=datetime.utcnow())
        )
        return result.rowcount > 0

    async def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        result = await self.session.execute(
            update(Agent)
            .where(Agent.id == agent_id)
            .values(status=status)
        )
        return result.rowcount > 0

    async def increment_stats(self, agent_id: str, success: bool, response_time: float):
        if success:
            await self.session.execute(
                update(Agent)
                .where(Agent.id == agent_id)
                .values(
                    total_tasks=Agent.total_tasks + 1,
                    success_count=Agent.success_count + 1,
                    total_response_time=Agent.total_response_time + response_time,
                    status=AgentStatus.IDLE,
                    current_task_id=None
                )
            )
        else:
            await self.session.execute(
                update(Agent)
                .where(Agent.id == agent_id)
                .values(
                    total_tasks=Agent.total_tasks + 1,
                    failure_count=Agent.failure_count + 1,
                    total_response_time=Agent.total_response_time + response_time,
                    status=AgentStatus.IDLE,
                    current_task_id=None
                )
            )

    async def count_by_status(self) -> dict:
        result = await self.session.execute(
            select(Agent.status, func.count(Agent.id))
            .group_by(Agent.status)
        )
        return dict(result.all())

    async def count_total(self) -> int:
        result = await self.session.execute(
            select(func.count(Agent.id))
        )
        return result.scalar() or 0

    async def get_all_capabilities(self) -> List[str]:
        result = await self.session.execute(select(Agent.capabilities))
        capabilities_list = result.scalars().all()
        all_capabilities = set()
        for caps in capabilities_list:
            if caps:
                all_capabilities.update(caps)
        return list(all_capabilities)
