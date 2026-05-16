import pytest
from datetime import datetime
from app.models.agent_data_model import Agent, AgentStatus
from app.schemas.agent_api_schemas import AgentCreate, AgentUpdate
from app.services.agent_lifecycle_management_service import AgentService
from app.repositories.agent_persistence_repository import AgentRepository
from app.core.custom_exceptions_handler import AgentNotFoundError

@pytest.mark.asyncio
class TestAgentService:
    """Unit tests for AgentService."""

    async def test_create_agent(self, db_session):
        """Test creating a new agent."""
        service = AgentService(db_session)
        data = AgentCreate(
            name="Test Agent",
            capabilities=["coding", "writing"],
            model="gpt-4",
            provider="openai"
        )
        
        agent = await service.create(data)
        
        assert agent.id is not None
        assert agent.name == "Test Agent"
        assert agent.capabilities == ["coding", "writing"]
        assert agent.model == "gpt-4"
        assert agent.status == AgentStatus.IDLE
        assert agent.total_tasks == 0

    async def test_get_agent(self, db_session):
        """Test retrieving an agent by ID."""
        service = AgentService(db_session)
        data = AgentCreate(name="Get Test Agent", capabilities=[], model="gpt-4", provider="openai")
        
        created = await service.create(data)
        retrieved = await service.get(created.id)
        
        assert retrieved.id == created.id
        assert retrieved.name == "Get Test Agent"

    async def test_get_agent_not_found(self, db_session):
        """Test retrieving non-existent agent raises error."""
        from app.core.custom_exceptions_handler import AgentNotFoundError
        
        service = AgentService(db_session)
        
        with pytest.raises(AgentNotFoundError):
            await service.get("non-existent-id")

    async def test_get_all_agents(self, db_session):
        """Test retrieving all agents."""
        service = AgentService(db_session)
        
        await service.create(AgentCreate(name="Agent 1", capabilities=[], model="gpt-4", provider="openai"))
        await service.create(AgentCreate(name="Agent 2", capabilities=[], model="gpt-3.5", provider="openai"))
        
        agents, total = await service.get_all()
        
        assert total == 2
        assert len(agents) == 2

    async def test_update_agent(self, db_session):
        """Test updating an agent."""
        service = AgentService(db_session)
        created = await service.create(AgentCreate(
            name="Original Name",
            capabilities=[],
            model="gpt-4",
            provider="openai"
        ))
        
        updated = await service.update(created.id, AgentUpdate(name="Updated Name"))
        
        assert updated.name == "Updated Name"

    async def test_delete_agent(self, db_session):
        """Test deleting an agent."""
        service = AgentService(db_session)
        created = await service.create(AgentCreate(
            name="To Delete",
            capabilities=[],
            model="gpt-4",
            provider="openai"
        ))
        
        success = await service.delete(created.id)
        
        assert success is True
        
        with pytest.raises(AgentNotFoundError):
            await service.get(created.id)

    async def test_heartbeat(self, db_session):
        """Test agent heartbeat update."""
        service = AgentService(db_session)
        created = await service.create(AgentCreate(
            name="Heartbeat Test",
            capabilities=[],
            model="gpt-4",
            provider="openai"
        ))
        
        success = await service.heartbeat(created.id)
        
        assert success is True

    async def test_get_stats(self, db_session):
        """Test getting agent statistics."""
        service = AgentService(db_session)
        
        await service.create(AgentCreate(name="Stats 1", capabilities=[], model="gpt-4", provider="openai"))
        await service.create(AgentCreate(name="Stats 2", capabilities=[], model="gpt-4", provider="openai"))
        
        stats = await service.get_stats()
        
        assert "total" in stats
        assert stats["total"] == 2
