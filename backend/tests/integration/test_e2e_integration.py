"""
End-to-end Integration Tests for Agent Cluster Orchestrator v2.0
"""
import pytest
import asyncio
import uuid
from httpx import AsyncClient

# Add backend to path
import sys
sys.path.insert(0, '/workspace/backend')

from app.main_fastapi_application import app
from app.multi_tenant.tenant_manager import tenant_manager
from app.config.dynamic_config_manager import config_manager


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def setup_test_tenant():
    """Setup a test tenant for all tests."""
    await tenant_manager.create_tenant(
        name="Test Tenant",
        domain="test.local"
    )
    yield
    # Cleanup
    tenants = await tenant_manager.list_tenants()
    for tenant in tenants:
        await tenant_manager.delete_tenant(tenant.id)


@pytest.mark.asyncio
class TestAPICrudOperations:
    """Test basic CRUD operations through API."""
    
    async def test_health_endpoint(self, client: AsyncClient):
        """Test health endpoint returns 200."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    async def test_create_and_get_agent(self, client: AsyncClient):
        """Test creating and retrieving an agent."""
        # Create agent
        create_response = await client.post(
            "/api/v1/agents",
            json={
                "name": "test-agent",
                "capabilities": ["data_analysis"],
                "model": "gpt-4",
                "provider": "openai"
            }
        )
        assert create_response.status_code == 201
        agent_id = create_response.json()["id"]
        
        # Get agent
        get_response = await client.get(f"/api/v1/agents/{agent_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "test-agent"
    
    async def test_create_and_get_task(self, client: AsyncClient):
        """Test creating and retrieving a task."""
        # Create task
        create_response = await client.post(
            "/api/v1/tasks",
            json={
                "description": "test task",
                "type": "data_analysis",
                "priority": 1,
                "input_data": {"test": "data"}
            }
        )
        assert create_response.status_code == 201
        task_id = create_response.json()["id"]
        
        # Get task
        get_response = await client.get(f"/api/v1/tasks/{task_id}")
        assert get_response.status_code == 200
        assert get_response.json()["description"] == "test task"


@pytest.mark.asyncio
class TestMultiTenant:
    """Test multi-tenant functionality."""
    
    async def test_create_tenant(self):
        """Test tenant creation."""
        tenant = await tenant_manager.create_tenant(
            name="Integration Test Tenant",
            domain="integration.test"
        )
        assert tenant.id is not None
        assert tenant.name == "Integration Test Tenant"
        assert tenant.status.value == "active"
    
    async def test_get_tenant_by_domain(self):
        """Test retrieving tenant by domain."""
        await tenant_manager.create_tenant(
            name="Domain Test Tenant",
            domain="domain.test"
        )
        
        tenant = await tenant_manager.get_tenant_by_domain("domain.test")
        assert tenant is not None
        assert tenant.name == "Domain Test Tenant"
    
    async def test_tenant_quota(self):
        """Test tenant quota configuration."""
        tenant = await tenant_manager.create_tenant(
            name="Quota Test Tenant",
            domain="quota.test"
        )
        
        assert tenant.quota.max_agents == 10
        assert tenant.quota.max_tasks == 100
        assert tenant.quota.max_concurrent_tasks == 10


@pytest.mark.asyncio
class TestDynamicConfig:
    """Test dynamic configuration management."""
    
    async def test_get_default_config(self):
        """Test getting default configuration."""
        value = await config_manager.get("app.name")
        assert value == "Agent Cluster Orchestrator"
    
    async def test_set_and_get_config(self):
        """Test setting and getting configuration."""
        await config_manager.set("test.key", "test.value")
        value = await config_manager.get("test.key")
        assert value == "test.value"
    
    async def test_config_validation(self):
        """Test configuration validation."""
        # This should fail due to validation (rate limit has max of 10000)
        with pytest.raises(ValueError):
            await config_manager.set("api.rate_limit", 20000)
    
    async def test_config_scope(self):
        """Test configuration scopes."""
        tenant_id = "test-tenant-id"
        
        # Set global value
        await config_manager.set("test.scoped.key", "global-value")
        
        # Set tenant-specific value
        await config_manager.set(
            "test.scoped.key", 
            "tenant-value", 
            scope="tenant", 
            tenant_id=tenant_id
        )
        
        # Should get tenant-specific value
        tenant_value = await config_manager.get(
            "test.scoped.key", 
            scope="tenant", 
            tenant_id=tenant_id
        )
        assert tenant_value == "tenant-value"
        
        # Should get global value for other scope
        global_value = await config_manager.get("test.scoped.key")
        assert global_value == "global-value"


@pytest.mark.asyncio
class TestPerformance:
    """Test performance-related functionality."""
    
    async def test_cache_performance(self):
        """Test cache operations."""
        from app.cache.cache_consistency import LRUCache
        
        cache = LRUCache(max_size=100)
        
        # Set multiple items
        for i in range(50):
            await cache.set(f"key-{i}", f"value-{i}")
        
        # Verify all items are cached
        for i in range(50):
            value = await cache.get(f"key-{i}")
            assert value == f"value-{i}"
        
        # Test LRU eviction
        for i in range(60):
            await cache.set(f"new-key-{i}", f"new-value-{i}")
        
        # First few original keys should be evicted
        value = await cache.get("key-0")
        assert value is None
        
        # Last original keys should still be there
        value = await cache.get("key-49")
        assert value == "value-49"
    
    async def test_retry_mechanism(self):
        """Test retry mechanism."""
        from app.tasks.task_retry_manager import RetryManager
        
        manager = RetryManager()
        call_count = 0
        
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Temporary failure")
            return "success"
        
        result = await manager.execute_with_retry("test-retry", flaky_function)
        assert result == "success"
        assert call_count == 3


@pytest.mark.asyncio
class TestSecurity:
    """Test security-related functionality."""
    
    async def test_security_headers(self, client: AsyncClient):
        """Test security headers are present."""
        response = await client.get("/health")
        
        headers = response.headers
        assert "x-content-type-options" in headers
        assert "x-frame-options" in headers
        assert headers["x-xss-protection"] == "1; mode=block"
    
    async def test_input_validation(self):
        """Test input validation utilities."""
        from app.core.security_utilities import InputValidator
        
        # Test email validation
        assert InputValidator.validate_email("test@example.com")
        assert not InputValidator.validate_email("invalid-email")
        
        # Test URL validation
        assert InputValidator.validate_url("https://example.com")
        assert not InputValidator.validate_url("not-a-url")
        
        # Test sanitization
        result = InputValidator.sanitize_string("<script>alert('xss')</script>")
        assert "<script>" not in result


def run_e2e_tests():
    """Run all end-to-end tests."""
    print("🚀 Running End-to-End Integration Tests")
    print("=" * 60)
    
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-x",
    ])


if __name__ == "__main__":
    run_e2e_tests()
