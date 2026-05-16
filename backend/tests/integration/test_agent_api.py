import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
class TestAgentAPI:
    """Integration tests for Agent API endpoints."""

    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    async def test_create_agent(self, client: AsyncClient):
        """Test creating an agent via API."""
        response = await client.post(
            "/api/v1/agents",
            json={
                "name": "API Test Agent",
                "capabilities": ["coding", "writing"],
                "model": "gpt-4",
                "provider": "openai"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "API Test Agent"
        assert data["capabilities"] == ["coding", "writing"]
        assert data["status"] == "idle"

    async def test_list_agents(self, client: AsyncClient):
        """Test listing agents."""
        await client.post(
            "/api/v1/agents",
            json={"name": "List Test 1", "capabilities": [], "model": "gpt-4", "provider": "openai"}
        )
        await client.post(
            "/api/v1/agents",
            json={"name": "List Test 2", "capabilities": [], "model": "gpt-4", "provider": "openai"}
        )
        
        response = await client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2

    async def test_get_agent(self, client: AsyncClient):
        """Test getting a specific agent."""
        create_response = await client.post(
            "/api/v1/agents",
            json={"name": "Get Test", "capabilities": [], "model": "gpt-4", "provider": "openai"}
        )
        agent_id = create_response.json()["id"]
        
        response = await client.get(f"/api/v1/agents/{agent_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Get Test"

    async def test_get_agent_not_found(self, client: AsyncClient):
        """Test getting non-existent agent returns 404."""
        response = await client.get("/api/v1/agents/non-existent-id")
        assert response.status_code == 404

    async def test_update_agent(self, client: AsyncClient):
        """Test updating an agent."""
        create_response = await client.post(
            "/api/v1/agents",
            json={"name": "Original", "capabilities": [], "model": "gpt-4", "provider": "openai"}
        )
        agent_id = create_response.json()["id"]
        
        response = await client.patch(
            f"/api/v1/agents/{agent_id}",
            json={"name": "Updated"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"

    async def test_delete_agent(self, client: AsyncClient):
        """Test deleting an agent."""
        create_response = await client.post(
            "/api/v1/agents",
            json={"name": "To Delete", "capabilities": [], "model": "gpt-4", "provider": "openai"}
        )
        agent_id = create_response.json()["id"]
        
        response = await client.delete(f"/api/v1/agents/{agent_id}")
        assert response.status_code == 204
        
        get_response = await client.get(f"/api/v1/agents/{agent_id}")
        assert get_response.status_code == 404

    async def test_agent_heartbeat(self, client: AsyncClient):
        """Test agent heartbeat."""
        create_response = await client.post(
            "/api/v1/agents",
            json={"name": "Heartbeat Test", "capabilities": [], "model": "gpt-4", "provider": "openai"}
        )
        agent_id = create_response.json()["id"]
        
        response = await client.post(f"/api/v1/agents/{agent_id}/heartbeat")
        assert response.status_code == 200

    async def test_get_agent_stats(self, client: AsyncClient):
        """Test getting agent statistics."""
        response = await client.get("/api/v1/agents/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "idle" in data
