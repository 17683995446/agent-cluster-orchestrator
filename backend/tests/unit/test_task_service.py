import pytest
from app.models.task_data_model import Task, TaskStatus
from app.schemas.task_api_schemas import TaskCreate, ClusterExecuteRequest
from app.services.task_dispatch_and_execution_service import TaskService
from app.services.agent_lifecycle_management_service import AgentService
from app.schemas.agent_api_schemas import AgentCreate
from app.core.custom_exceptions_handler import TaskNotFoundError

@pytest.mark.asyncio
class TestTaskService:
    """Unit tests for TaskService."""

    async def test_create_task(self, db_session):
        """Test creating a new task."""
        service = TaskService(db_session)
        data = TaskCreate(
            description="Test task description",
            priority=5
        )
        
        task = await service.create(data)
        
        assert task.id is not None
        assert task.description == "Test task description"
        assert task.priority == 5
        assert task.status == TaskStatus.PENDING

    async def test_get_task(self, db_session):
        """Test retrieving a task by ID."""
        task_service = TaskService(db_session)
        data = TaskCreate(description="Get Test Task", priority=0)
        
        created = await task_service.create(data)
        retrieved = await task_service.get(created.id)
        
        assert retrieved.id == created.id
        assert retrieved.description == "Get Test Task"

    async def test_get_task_not_found(self, db_session):
        """Test retrieving non-existent task raises error."""
        service = TaskService(db_session)
        
        with pytest.raises(TaskNotFoundError):
            await service.get("non-existent-id")

    async def test_get_all_tasks(self, db_session):
        """Test retrieving all tasks."""
        service = TaskService(db_session)
        
        await service.create(TaskCreate(description="Task 1", priority=1))
        await service.create(TaskCreate(description="Task 2", priority=2))
        await service.create(TaskCreate(description="Task 3", priority=3))
        
        tasks, total = await service.get_all()
        
        assert total == 3
        assert len(tasks) == 3

    async def test_cancel_task(self, db_session):
        """Test cancelling a task."""
        service = TaskService(db_session)
        task = await service.create(TaskCreate(description="Cancel Test", priority=0))
        
        success = await service.cancel(task.id)
        
        assert success is True
        
        cancelled = await service.get(task.id)
        assert cancelled.status == TaskStatus.CANCELLED

    async def test_cluster_stats(self, db_session):
        """Test getting cluster statistics."""
        agent_service = AgentService(db_session)
        task_service = TaskService(db_session)
        
        await agent_service.create(AgentCreate(name="Agent 1", capabilities=[], model="gpt-4", provider="openai"))
        await task_service.create(TaskCreate(description="Task 1", priority=0))
        await task_service.create(TaskCreate(description="Task 2", priority=0))
        
        stats = await task_service.get_cluster_stats()
        
        assert stats.total_agents == 1
        assert stats.total_tasks == 2
        assert stats.pending_tasks == 2

    async def test_capability_inference(self, db_session):
        """Test automatic capability inference from task description."""
        service = TaskService(db_session)
        
        code_caps = service._infer_capabilities("帮我写一段Python代码")
        assert "code_generation" in code_caps
        
        analysis_caps = service._infer_capabilities("分析这些数据的趋势")
        assert "data_analysis" in analysis_caps
        
        writing_caps = service._infer_capabilities("写一篇关于AI的文章")
        assert "writing" in writing_caps

    async def test_decompose_task(self, db_session):
        """Test task decomposition returns list."""
        service = TaskService(db_session)
        
        parts = await service._decompose_task("Complex task", 3)
        
        assert isinstance(parts, list)
        assert len(parts) <= 3
