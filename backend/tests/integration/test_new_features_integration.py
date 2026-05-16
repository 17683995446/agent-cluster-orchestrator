import pytest
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.security.jwt_authentication import JWTManager


@pytest.fixture
def jwt_manager():
    return JWTManager(
        secret_key="test-secret-key-for-testing-purposes-only",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7
    )


class TestJWTManager:
    def test_create_access_token(self, jwt_manager):
        token, expire = jwt_manager.create_access_token(
            subject="user123",
            username="testuser",
            role="admin"
        )
        assert token is not None
        assert expire > datetime.utcnow()
        assert expire <= datetime.utcnow() + timedelta(minutes=31)

    def test_create_refresh_token(self, jwt_manager):
        token, expire = jwt_manager.create_refresh_token(
            subject="user123",
            username="testuser"
        )
        assert token is not None
        assert expire > datetime.utcnow()

    def test_decode_token(self, jwt_manager):
        token, _ = jwt_manager.create_access_token(
            subject="user123",
            username="testuser",
            role="admin"
        )
        payload = jwt_manager.decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["username"] == "testuser"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_verify_access_token_valid(self, jwt_manager):
        token, _ = jwt_manager.create_access_token(
            subject="user123",
            username="testuser",
            role="admin"
        )
        payload = jwt_manager.verify_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"

    def test_verify_access_token_invalid(self, jwt_manager):
        payload = jwt_manager.verify_access_token("invalid_token")
        assert payload is None

    def test_verify_refresh_token_valid(self, jwt_manager):
        token, _ = jwt_manager.create_refresh_token(
            subject="user123",
            username="testuser"
        )
        payload = jwt_manager.verify_refresh_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["type"] == "refresh"

    def test_verify_refresh_token_wrong_type(self, jwt_manager):
        access_token, _ = jwt_manager.create_access_token(
            subject="user123",
            username="testuser",
            role="admin"
        )
        payload = jwt_manager.verify_refresh_token(access_token)
        assert payload is None

    def test_token_with_additional_claims(self, jwt_manager):
        token, _ = jwt_manager.create_access_token(
            subject="user123",
            username="testuser",
            role="admin",
            additional_claims={"custom_claim": "value"}
        )
        payload = jwt_manager.decode_token(token)
        assert payload["custom_claim"] == "value"


class TestExceptionHandlers:
    def test_agent_cluster_exception_structure(self):
        from app.core.enhanced_exception_handler import AgentClusterException
        exc = AgentClusterException(
            code="TEST_ERROR",
            message="Test message",
            status_code=400
        )
        assert exc.code == "TEST_ERROR"
        assert exc.message == "Test message"
        assert exc.status_code == 400

    def test_resource_not_found_exception(self):
        from app.core.enhanced_exception_handler import ResourceNotFoundException
        exc = ResourceNotFoundException("Agent", "agent-123")
        assert exc.code == "RESOURCE_NOT_FOUND"
        assert "Agent" in exc.message
        assert "agent-123" in exc.message
        assert exc.status_code == 404

    def test_rate_limit_exception(self):
        from app.core.enhanced_exception_handler import RateLimitExceededException
        exc = RateLimitExceededException(retry_after=120)
        assert exc.code == "RATE_LIMIT_EXCEEDED"
        assert exc.status_code == 429
        assert exc.details["retry_after"] == 120

    def test_circuit_breaker_exception(self):
        from app.core.enhanced_exception_handler import CircuitBreakerOpenException
        exc = CircuitBreakerOpenException(service_name="openai")
        assert exc.code == "CIRCUIT_BREAKER_OPEN"
        assert exc.status_code == 503
        assert exc.details["service_name"] == "openai"


class TestCacheStrategy:
    def test_cache_entry_expiration(self):
        from app.cache.advanced_cache_strategy_manager import CacheEntry
        from datetime import timedelta

        entry = CacheEntry(
            key="test",
            value="data",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=60)
        )
        assert not entry.is_expired()

        entry_expired = CacheEntry(
            key="test",
            value="data",
            created_at=datetime.utcnow() - timedelta(seconds=120),
            expires_at=datetime.utcnow() - timedelta(seconds=60)
        )
        assert entry_expired.is_expired()

    def test_cache_entry_no_expiration(self):
        from app.cache.advanced_cache_strategy_manager import CacheEntry

        entry = CacheEntry(
            key="test",
            value="data",
            created_at=datetime.utcnow()
        )
        assert not entry.is_expired()

    def test_cache_key_builder(self):
        from app.cache.advanced_cache_strategy_manager import CacheKeyBuilder

        key = CacheKeyBuilder.build("prefix", "resource", "id")
        assert "prefix" in key
        assert "resource" in key
        assert "id" in key

        key_with_none = CacheKeyBuilder.build("prefix", None, "value")
        assert "prefix" in key_with_none
        assert "value" in key_with_none

    def test_cache_key_builder_pattern(self):
        from app.cache.advanced_cache_strategy_manager import CacheKeyBuilder

        key = CacheKeyBuilder.build_pattern("agents", status="active", type="worker")
        assert "agents" in key
        assert "status:active" in key
        assert "type:worker" in key

    def test_cache_metrics(self):
        from app.cache.advanced_cache_strategy_manager import CacheMetrics

        metrics = CacheMetrics()
        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.writes == 0
        assert metrics.hit_rate == 0.0

        metrics.hits = 80
        metrics.misses = 20
        total = metrics.hits + metrics.misses
        metrics.hit_rate = (metrics.hits / total * 100) if total > 0 else 0.0
        assert metrics.hit_rate == 80.0


class TestWebSocketConnectionManager:
    def test_message_type_enum(self):
        from app.websocket.websocket_connection_manager import MessageType

        assert MessageType.AGENT_STATUS_CHANGE == "agent_status_change"
        assert MessageType.TASK_CREATED == "task_created"
        assert MessageType.NOTIFICATION == "notification"
        assert MessageType.HEARTBEAT == "heartbeat"

    def test_connection_state_enum(self):
        from app.websocket.websocket_connection_manager import ConnectionState

        assert ConnectionState.CONNECTED == "connected"
        assert ConnectionState.DISCONNECTED == "disconnected"
        assert ConnectionState.AUTHENTICATED == "authenticated"
