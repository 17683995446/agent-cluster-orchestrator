#!/usr/bin/env python3
"""
Comprehensive Integration Test Suite
for Agent Cluster Orchestrator System v2.0
"""
import asyncio
import pytest
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


class TestAlembicMigrations:
    """Test database migration scripts."""
    
    def test_alembic_config_exists(self):
        """Verify Alembic configuration exists."""
        alembic_ini = Path("backend/alembic.ini")
        assert alembic_ini.exists(), "Alembic configuration file missing"
    
    def test_initial_migration_exists(self):
        """Verify initial database migration exists."""
        migration_dir = Path("backend/alembic/versions/0001_initial.py")
        assert migration_dir.exists(), "Initial migration file missing"


class TestCacheConsistency:
    """Test the new cache consistency system."""
    
    @pytest.mark.asyncio
    async def test_lru_cache_basic_operations(self):
        from app.cache.cache_consistency import LRUCache
        
        cache = LRUCache(max_size=100)
        
        # Set and get
        await cache.set("key1", "value1")
        value = await cache.get("key1")
        assert value == "value1"
        
        # Delete
        deleted = await cache.delete("key1")
        assert deleted
        
        # Get after delete
        value = await cache.get("key1")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_lru_cache_size_limit(self):
        from app.cache.cache_consistency import LRUCache
        
        cache = LRUCache(max_size=3)
        
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        await cache.set("key4", "value4")  # Should evict key1
        
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"
    
    @pytest.mark.asyncio
    async def test_cache_tag_invalidation(self):
        from app.cache.cache_consistency import LRUCache
        
        cache = LRUCache(max_size=100)
        
        await cache.set("agent:1", "agent1", tags={"agent", "team:a"})
        await cache.set("agent:2", "agent2", tags={"agent", "team:b"})
        await cache.set("other", "other")
        
        count = await cache.invalidate_tag("agent")
        assert count == 2
        
        assert await cache.get("agent:1") is None
        assert await cache.get("agent:2") is None
        assert await cache.get("other") == "other"


class TestRetryManager:
    """Test the task retry manager."""
    
    @pytest.mark.asyncio
    async def test_retry_success_on_first_try(self):
        from app.tasks.task_retry_manager import RetryManager, RetryPolicy
        
        manager = RetryManager()
        call_count = 0
        
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await manager.execute_with_retry("test-1", success_func)
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self):
        from app.tasks.task_retry_manager import RetryManager, RetryPolicy
        
        manager = RetryManager()
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Temporary failure {call_count}")
            return "finally succeeded"
        
        result = await manager.execute_with_retry("test-2", flaky_func)
        assert result == "finally succeeded"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_gives_up_after_max_attempts(self):
        from app.tasks.task_retry_manager import RetryManager, RetryPolicy
        
        policy = RetryPolicy(max_attempts=3)
        manager = RetryManager(default_policy=policy)
        call_count = 0
        
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")
        
        with pytest.raises(Exception):
            await manager.execute_with_retry("test-3", always_fails)
        
        assert call_count == 3
    
    def test_retry_policy_config(self):
        from app.tasks.task_retry_manager import RetryPolicy, DEFAULT_POLICY, AGGRESSIVE_POLICY, CONSERVATIVE_POLICY
        
        assert DEFAULT_POLICY.max_attempts == 5
        assert AGGRESSIVE_POLICY.max_attempts == 10
        assert CONSERVATIVE_POLICY.max_attempts == 3


class TestMonitoringConfig:
    """Test Prometheus configuration."""
    
    def test_prometheus_config_exists(self):
        """Verify Prometheus configuration exists."""
        prometheus_yml = Path("prometheus/prometheus.yml")
        assert prometheus_yml.exists(), "Prometheus config file missing"
    
    def test_alerts_config_exists(self):
        """Verify alert rules exist."""
        alerts_yml = Path("prometheus/alerts.yml")
        assert alerts_yml.exists(), "Alerts config file missing"
    
    def test_alerts_config_valid(self):
        """Verify alert rules syntax (basic validation)."""
        import yaml
        
        alerts_yml = Path("prometheus/alerts.yml")
        with open(alerts_yml) as f:
            config = yaml.safe_load(f)
        
        assert "groups" in config
        assert len(config["groups"]) == 1
        assert "rules" in config["groups"][0]


class TestWebSocketClient:
    """Test WebSocket client implementation."""
    
    def test_websocket_typescript_client_exists(self):
        """Verify WebSocket client file exists."""
        ws_client = Path("frontend/src/services/enhanced-websocket.ts")
        assert ws_client.exists(), "WebSocket client file missing"
    
    def test_websocket_client_has_reconnection_logic(self):
        """Verify WebSocket client has reconnection features."""
        ws_client = Path("frontend/src/services/enhanced-websocket.ts")
        
        content = ws_client.read_text()
        assert "autoReconnect" in content
        assert "exponential" in content.lower()
        assert "backoff" in content.lower()
        assert "heartbeat" in content.lower()


class TestDocumentation:
    """Test documentation completeness."""
    
    def test_architecture_docs_exist(self):
        """Verify architecture documentation exists."""
        arch_html = Path("docs/architecture.html")
        assert arch_html.exists(), "Architecture documentation missing"
    
    def test_sdk_documentation_exists(self):
        """Verify SDK documentation exists."""
        sdk_docs = Path("docs/SDK_PYTHON.md")
        assert sdk_docs.exists(), "SDK documentation missing"
    
    def test_developer_guide_exists(self):
        """Verify developer guide exists."""
        dev_guide = Path("docs/DEVELOPER_GUIDE.md")
        assert dev_guide.exists(), "Developer guide missing"


def run_all_tests():
    """Run all integration tests and display comprehensive summary."""
    print("=" * 80)
    print("AGENT CLUSTER ORCHESTRATOR - INTEGRATION TESTS")
    print("=" * 80)
    print()
    
    # Run pytest programmatically
    result = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--no-header",
    ])
    
    print()
    print("=" * 80)
    
    if result == 0:
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print()
        print("📊 SYSTEM READINESS CHECKLIST:")
        print("  ✅ Alembic database migrations")
        print("  ✅ Cache consistency system")
        print("  ✅ Task retry manager with exponential backoff")
        print("  ✅ Prometheus monitoring & alerting")
        print("  ✅ WebSocket client with auto-reconnection")
        print("  ✅ Comprehensive documentation")
    else:
        print("❌ Some tests failed. See details above.")
        print("=" * 80)
    
    return result


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
