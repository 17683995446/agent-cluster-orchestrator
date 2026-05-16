import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
class TestTaskAPI:
    """Integration tests for Task API endpoints."""

    async def test_create_task(self, client: AsyncClient):
        """Test creating a task via API."""
        response = await client.post(
            "/api/v1/tasks",
            json={
                "description": "Test task description",
                "priority": 5
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["description"] == "Test task description"
        assert data["priority"] == 5
        assert data["status"] == "pending"

    async def test_list_tasks(self, client: AsyncClient):
        """Test listing tasks."""
        await client.post(
            "/api/v1/tasks",
            json={"description": "Task 1", "priority": 1}
        )
        await client.post(
            "/api/v1/tasks",
            json={"description": "Task 2", "priority": 2}
        )
        
        response = await client.get("/api/v1/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    async def test_get_task(self, client: AsyncClient):
        """Test getting a specific task."""
        create_response = await client.post(
            "/api/v1/tasks",
            json={"description": "Get Test Task", "priority": 0}
        )
        task_id = create_response.json()["id"]
        
        response = await client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["description"] == "Get Test Task"

    async def test_get_task_not_found(self, client: AsyncClient):
        """Test getting non-existent task returns 404."""
        response = await client.get("/api/v1/tasks/non-existent-id")
        assert response.status_code == 404

    async def test_cancel_task(self, client: AsyncClient):
        """Test cancelling a task."""
        create_response = await client.post(
            "/api/v1/tasks",
            json={"description": "Cancel Test", "priority": 0}
        )
        task_id = create_response.json()["id"]
        
        response = await client.delete(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 204
        
        get_response = await client.get(f"/api/v1/tasks/{task_id}")
        assert get_response.json()["status"] == "cancelled"

    async def test_get_task_result(self, client: AsyncClient):
        """Test getting task result."""
        create_response = await client.post(
            "/api/v1/tasks",
            json={"description": "Result Test", "priority": 0}
        )
        task_id = create_response.json()["id"]
        
        response = await client.get(f"/api/v1/tasks/{task_id}/result")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "task_id" in data

    async def test_pagination(self, client: AsyncClient):
        """Test task pagination."""
        for i in range(5):
            await client.post(
                "/api/v1/tasks",
                json={"description": f"Task {i}", "priority": i}
            )
        
        response = await client.get("/api/v1/tasks?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2

@pytest.mark.asyncio
class TestClusterAPI:
    """Integration tests for Cluster API endpoints."""

    async def test_cluster_stats(self, client: AsyncClient):
        """Test getting cluster statistics."""
        response = await client.get("/api/v1/cluster/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_agents" in data
        assert "total_tasks" in data
        assert "success_rate" in data

    async def test_execute_cluster_task(self, client: AsyncClient):
        """Test executing a cluster task."""
        response = await client.post(
            "/api/v1/cluster/execute",
            json={
                "description": "Complex task that needs decomposition",
                "num_agents": 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "parent_task_id" in data
        assert "subtask_ids" in data
        assert data["status"] == "scheduled"
