"""
Phase 1: 深度测试体系完善
Unit Tests for Enhanced Task Service
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.enhanced_task_service import (
    EnhancedTaskService,
    ConcurrencyController,
    TaskExecutionContext
)
from app.models.task_data_model import Task, TaskStatus
from app.models.agent_data_model import Agent, AgentStatus


class TestConcurrencyController:
    """Tests for ConcurrencyController."""

    @pytest.fixture
    def controller(self):
        """Create a fresh controller for each test."""
        return ConcurrencyController(
            max_concurrent_per_agent=2,
            max_global_concurrent=5
        )

    @pytest.mark.asyncio
    async def test_acquire_new_agent_semaphore(self, controller):
        """Test acquiring semaphore for new agent."""
        semaphore = await controller.acquire("agent-1")
        assert semaphore is not None
        assert isinstance(semaphore, asyncio.Semaphore)

    @pytest.mark.asyncio
    async def test_acquire_existing_agent_semaphore(self, controller):
        """Test acquiring same semaphore for existing agent."""
        sem1 = await controller.acquire("agent-1")
        sem2 = await controller.acquire("agent-1")
        assert sem1 is sem2

    @pytest.mark.asyncio
    async def test_limit_concurrency_single_task(self, controller):
        """Test single task can acquire concurrency slot."""
        async with controller.limit_concurrency("agent-1", "task-1"):
            assert len(controller._active_tasks) == 1
            assert "task-1" in controller._active_tasks
        
        assert len(controller._active_tasks) == 0

    @pytest.mark.asyncio
    async def test_limit_concurrency_multiple_tasks(self, controller):
        """Test multiple tasks can run concurrently within limits."""
        tasks_results = []
        
        async def run_task(agent_id, task_id):
            async with controller.limit_concurrency(agent_id, task_id):
                tasks_results.append(task_id)
                await asyncio.sleep(0.1)
        
        await asyncio.gather(
            run_task("agent-1", "task-1"),
            run_task("agent-1", "task-2"),
        )
        
        assert len(tasks_results) == 2
        assert "task-1" in tasks_results
        assert "task-2" in tasks_results

    @pytest.mark.asyncio
    async def test_global_concurrency_limit(self, controller):
        """Test global concurrency limit is enforced."""
        max_concurrent = 0
        active_tasks = []
        
        async def run_task(task_id):
            nonlocal max_concurrent
            async with controller.limit_concurrency("agent-1", task_id):
                active_tasks.append(task_id)
                max_concurrent = max(max_concurrent, len(controller._active_tasks))
                await asyncio.sleep(0.05)
                active_tasks.remove(task_id)
        
        tasks = [run_task(f"task-{i}") for i in range(10)]
        await asyncio.gather(*tasks)
        
        assert max_concurrent <= controller._max_per_agent

    def test_get_active_count(self, controller):
        """Test getting active task count."""
        assert controller.get_active_count() == 0


class TestEnhancedTaskService:
    """Tests for EnhancedTaskService."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def mock_task_repo(self):
        """Create mock task repository."""
        repo = MagicMock()
        repo.create = AsyncMock()
        repo.get_by_id = AsyncMock()
        repo.update_status = AsyncMock(return_value=True)
        repo.set_result = AsyncMock()
        repo.set_error = AsyncMock()
        repo.assign_agent = AsyncMock()
        return repo

    @pytest.fixture
    def mock_agent_repo(self):
        """Create mock agent repository."""
        repo = MagicMock()
        repo.update_status = AsyncMock(return_value=True)
        repo.increment_stats = AsyncMock()
        repo.get_idle_agents = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def service(self, mock_session, mock_task_repo, mock_agent_repo):
        """Create service with mocked dependencies."""
        service = EnhancedTaskService(mock_session)
        service.task_repo = mock_task_repo
        service.agent_repo = mock_agent_repo
        return service

    @pytest.mark.asyncio
    async def test_create_task(self, service, mock_task_repo):
        """Test task creation."""
        from app.schemas.task_api_schemas import TaskCreate, TaskType
        
        task_data = TaskCreate(
            description="Test task",
            priority=1,
            type=TaskType.SINGLE
        )
        
        mock_task = MagicMock(spec=Task)
        mock_task.id = "test-task-id"
        mock_task.description = "Test task"
        mock_task_repo.create.return_value = mock_task
        
        task = await service.create(task_data)
        
        assert task.id == "test-task-id"
        mock_task_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_task_no_idle_agents(self, service, mock_agent_repo):
        """Test scheduling when no agents available."""
        mock_agent_repo.get_idle_agents.return_value = []
        
        result = await service.schedule_task("task-1")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_schedule_task_with_agent(
        self, service, mock_task_repo, mock_agent_repo
    ):
        """Test scheduling with available agent."""
        mock_task = MagicMock(spec=Task)
        mock_task.id = "task-1"
        mock_task.status = TaskStatus.PENDING
        mock_task.description = "Test"
        
        mock_agent = MagicMock(spec=Agent)
        mock_agent.id = "agent-1"
        mock_agent.status = AgentStatus.IDLE
        
        mock_task_repo.get_by_id.return_value = mock_task
        mock_agent_repo.get_idle_agents.return_value = [mock_agent]
        
        result = await service.schedule_task("task-1")
        
        assert result == "agent-1"
        mock_agent_repo.update_status.assert_called()

    @pytest.mark.asyncio
    async def test_cancel_task(self, service, mock_task_repo, mock_agent_repo):
        """Test task cancellation."""
        mock_task = MagicMock(spec=Task)
        mock_task.id = "task-1"
        mock_task.status = TaskStatus.RUNNING
        mock_task.assigned_agent_id = "agent-1"
        
        mock_task_repo.get_by_id.return_value = mock_task
        
        result = await service.cancel("task-1")
        
        assert result is True
        mock_task_repo.update_status.assert_called()

    @pytest.mark.asyncio
    async def test_infer_capabilities_code_generation(self, service):
        """Test capability inference for code generation."""
        capabilities = service._infer_capabilities("请帮我写一段Python代码")
        assert "code_generation" in capabilities

    @pytest.mark.asyncio
    async def test_infer_capabilities_data_analysis(self, service):
        """Test capability inference for data analysis."""
        capabilities = service._infer_capabilities("分析这份销售数据")
        assert "data_analysis" in capabilities

    @pytest.mark.asyncio
    async def test_infer_capabilities_translation(self, service):
        """Test capability inference for translation."""
        capabilities = service._infer_capabilities("翻译成英文")
        assert "translation" in capabilities

    @pytest.mark.asyncio
    async def test_infer_capabilities_default(self, service):
        """Test capability inference default case."""
        capabilities = service._infer_capabilities("random text")
        assert "general" in capabilities


class TestTaskExecutionContext:
    """Tests for TaskExecutionContext."""

    @pytest.mark.asyncio
    async def test_context_enter_exit(self):
        """Test context manager enter and exit."""
        mock_service = MagicMock()
        context = TaskExecutionContext(mock_service, "task-1", "agent-1")
        
        async with context as ctx:
            assert ctx is context
            assert context.start_time is not None
        
        # After exit, duration should be calculated
        assert context.start_time is not None

    @pytest.mark.asyncio
    async def test_context_with_exception(self):
        """Test context manager handles exceptions."""
        mock_service = MagicMock()
        context = TaskExecutionContext(mock_service, "task-1", "agent-1")
        
        with pytest.raises(ValueError):
            async with context:
                raise ValueError("Test error")
        
        assert context.start_time is not None


class TestConcurrencyIntegration:
    """Integration tests for concurrency handling."""

    @pytest.mark.asyncio
    async def test_concurrent_task_execution(self):
        """Test multiple tasks can execute concurrently."""
        controller = ConcurrencyController(
            max_concurrent_per_agent=3,
            max_global_concurrent=10
        )
        
        execution_order = []
        
        async def simulate_task(agent_id, task_id, duration):
            async with controller.limit_concurrency(agent_id, task_id):
                execution_order.append(f"start-{task_id}")
                await asyncio.sleep(duration)
                execution_order.append(f"end-{task_id}")
        
        tasks = [
            simulate_task("agent-1", "task-1", 0.1),
            simulate_task("agent-1", "task-2", 0.1),
            simulate_task("agent-1", "task-3", 0.1),
        ]
        
        await asyncio.gather(*tasks)
        
        assert len(execution_order) == 6
        for i in range(1, 4):
            start_idx = execution_order.index(f"start-task-{i}")
            end_idx = execution_order.index(f"end-task-{i}")
            assert start_idx < end_idx

    @pytest.mark.asyncio
    async def test_semaphore_per_agent(self):
        """Test each agent has its own semaphore limit."""
        controller = ConcurrencyController(
            max_concurrent_per_agent=1,
            max_global_concurrent=10
        )
        
        agent1_tasks = []
        agent2_tasks = []
        
        async def task_for_agent(agent_id, task_id):
            async with controller.limit_concurrency(agent_id, task_id):
                if agent_id == "agent-1":
                    agent1_tasks.append(task_id)
                else:
                    agent2_tasks.append(task_id)
                await asyncio.sleep(0.05)
        
        tasks = [
            task_for_agent("agent-1", "task-1"),
            task_for_agent("agent-1", "task-2"),
            task_for_agent("agent-2", "task-3"),
            task_for_agent("agent-2", "task-4"),
        ]
        
        await asyncio.gather(*tasks)
        
        # Agent 1 tasks should not overlap
        assert len(agent1_tasks) == 2
        # Agent 2 tasks should not overlap
        assert len(agent2_tasks) == 2


class TestRetryBehavior:
    """Tests for retry behavior in task execution."""

    @pytest.mark.asyncio
    async def test_cleanup_on_failure(self):
        """Test cleanup is performed on task failure."""
        mock_session = MagicMock()
        service = EnhancedTaskService(mock_session)
        
        mock_task_repo = MagicMock()
        mock_agent_repo = MagicMock()
        mock_task_repo.set_error = AsyncMock()
        mock_task_repo.update_status = AsyncMock()
        mock_agent_repo.increment_stats = AsyncMock()
        mock_agent_repo.update_status = AsyncMock()
        
        service.task_repo = mock_task_repo
        service.agent_repo = mock_agent_repo
        
        await service._cleanup_failed_task("task-1", "agent-1", "Test error")
        
        mock_task_repo.set_error.assert_called_once_with("task-1", "Test error")
        mock_task_repo.update_status.assert_called()
        mock_agent_repo.increment_stats.assert_called_once()
        mock_agent_repo.update_status.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
