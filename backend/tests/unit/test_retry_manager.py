"""
Phase 1: 深度测试体系完善
Unit Tests for Optimized Retry Manager
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from app.tasks.optimized_retry_manager import (
    OptimizedRetryManager,
    RetryPolicy,
    RetryStrategy,
    BackoffCalculator,
    CircuitBreaker,
    CircuitState,
    AdaptiveRetryPolicy
)


class TestBackoffCalculator:
    """Tests for BackoffCalculator."""

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        policy = RetryPolicy(
            initial_delay=1.0,
            max_delay=60.0,
            backoff_multiplier=2.0,
            jitter_factor=0.0
        )
        
        delay1 = BackoffCalculator.exponential(0, 1.0, 60.0, 2.0, 0.0)
        delay2 = BackoffCalculator.exponential(1, 1.0, 60.0, 2.0, 0.0)
        delay3 = BackoffCalculator.exponential(2, 1.0, 60.0, 2.0, 0.0)
        
        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 4.0

    def test_exponential_backoff_with_jitter(self):
        """Test exponential backoff with jitter."""
        delays = []
        for _ in range(10):
            delay = BackoffCalculator.exponential(2, 1.0, 60.0, 2.0, 0.1)
            delays.append(delay)
        
        # With jitter, delays should vary
        assert len(set(delays)) > 1
        # But should still be around the base value
        assert all(3.0 <= d <= 5.0 for d in delays)

    def test_linear_backoff(self):
        """Test linear backoff calculation."""
        delay0 = BackoffCalculator.linear(0, 1.0, 60.0, 1.0, 0.0)
        delay1 = BackoffCalculator.linear(1, 1.0, 60.0, 1.0, 0.0)
        delay2 = BackoffCalculator.linear(2, 1.0, 60.0, 1.0, 0.0)
        
        assert delay0 == 1.0
        assert delay1 == 2.0
        assert delay2 == 3.0

    def test_fibonacci_backoff(self):
        """Test Fibonacci backoff calculation."""
        delay0 = BackoffCalculator.fibonacci(0, 1.0, 60.0, 1.0, 0.0)
        delay1 = BackoffCalculator.fibonacci(1, 1.0, 60.0, 1.0, 0.0)
        delay2 = BackoffCalculator.fibonacci(2, 1.0, 60.0, 1.0, 0.0)
        delay3 = BackoffCalculator.fibonacci(3, 1.0, 60.0, 1.0, 0.0)
        
        # Fibonacci sequence: 1, 1, 2, 3
        assert delay0 == 1.0
        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 3.0

    def test_decorrelated_jitter(self):
        """Test decorrelated jitter backoff."""
        delays = []
        prev_delay = 0.0
        for _ in range(10):
            delay = BackoffCalculator.decorrelated_jitter(
                2, 1.0, 60.0, 3.0, 0.2, prev_delay
            )
            delays.append(delay)
            prev_delay = delay
        
        # Decorrelated jitter should produce varied delays
        assert len(set(delays)) > 1

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        delay = BackoffCalculator.exponential(10, 1.0, 10.0, 2.0, 0.0)
        assert delay == 10.0

    def test_calculate_with_strategy(self):
        """Test calculate method dispatches to correct strategy."""
        policy = RetryPolicy(
            initial_delay=1.0,
            max_delay=60.0,
            backoff_multiplier=2.0,
            jitter_factor=0.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )
        
        delay = BackoffCalculator.calculate(
            RetryStrategy.EXPONENTIAL_BACKOFF,
            2,
            policy
        )
        
        assert delay == 4.0


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create a fresh circuit breaker for each test."""
        return CircuitBreaker(
            failure_threshold=3,
            reset_timeout=30.0,
            half_open_requests=1
        )

    @pytest.mark.asyncio
    async def test_initial_state_closed(self, circuit_breaker):
        """Test circuit breaker starts in closed state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        is_open = await circuit_breaker.is_open()
        assert is_open is False

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self, circuit_breaker):
        """Test circuit breaker opens after threshold failures."""
        for _ in range(3):
            await circuit_breaker.record_failure()
        
        is_open = await circuit_breaker.is_open()
        assert is_open is True
        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self, circuit_breaker):
        """Test success resets failure count."""
        await circuit_breaker.record_failure()
        await circuit_breaker.record_failure()
        await circuit_breaker.record_success()
        
        # Should not open after just 1 failure now
        is_open = await circuit_breaker.is_open()
        assert is_open is False

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self, circuit_breaker):
        """Test circuit breaker goes half-open after timeout."""
        for _ in range(3):
            await circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Manually check state after timeout
        with patch('datetime.datetime') as mock_dt:
            mock_dt.now.return_value.timestamp.return_value = (
                circuit_breaker._last_failure_time + 31.0
            )
            state = await circuit_breaker.get_state()
            assert state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_to_closed_on_success(self, circuit_breaker):
        """Test circuit breaker closes after successful half-open request."""
        for _ in range(3):
            await circuit_breaker.record_failure()
        
        # Simulate timeout
        circuit_breaker._state = CircuitState.HALF_OPEN
        
        await circuit_breaker.record_success()
        assert circuit_breaker.state == CircuitState.CLOSED


class TestOptimizedRetryManager:
    """Tests for OptimizedRetryManager."""

    @pytest.fixture
    def default_policy(self):
        """Create default retry policy."""
        return RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=1.0,
            backoff_multiplier=2.0,
            jitter_factor=0.0
        )

    @pytest.fixture
    def retry_manager(self, default_policy):
        """Create retry manager with default policy."""
        return OptimizedRetryManager(default_policy)

    @pytest.mark.asyncio
    async def test_successful_execution(self, retry_manager):
        """Test successful function execution."""
        async def success_func():
            return "success"
        
        result = await retry_manager.execute_with_retry(
            "test-task-1",
            success_func
        )
        
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, retry_manager):
        """Test retry on transient failure."""
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return "success after retries"
        
        result = await retry_manager.execute_with_retry(
            "test-task-2",
            flaky_func
        )
        
        assert result == "success after retries"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self, retry_manager):
        """Test exception raised after max attempts."""
        call_count = 0
        
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Persistent error")
        
        with pytest.raises(Exception):
            await retry_manager.execute_with_retry(
                "test-task-3",
                always_fails
            )
        
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_custom_policy(self, default_policy):
        """Test retry with custom policy."""
        custom_policy = RetryPolicy(
            max_attempts=2,
            initial_delay=0.01,
            max_delay=0.1
        )
        
        manager = OptimizedRetryManager(custom_policy)
        call_count = 0
        
        async def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Fail once")
            return "success"
        
        result = await manager.execute_with_retry(
            "test-task-4",
            fails_once
        )
        
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, default_policy):
        """Test circuit breaker integration with retry manager."""
        manager = OptimizedRetryManager(default_policy)
        
        call_count = 0
        
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")
        
        with pytest.raises(Exception):
            await manager.execute_with_retry(
                "test-task-5",
                always_fails
            )
        
        # Circuit breaker should have recorded failures
        assert call_count == default_policy.max_attempts

    @pytest.mark.asyncio
    async def test_get_record(self, retry_manager):
        """Test getting retry record for task."""
        async def success_func():
            return "success"
        
        await retry_manager.execute_with_retry(
            "test-task-6",
            success_func
        )
        
        record = await retry_manager.get_record("test-task-6")
        assert record is not None
        assert record.status.value == 3  # SUCCESS

    @pytest.mark.asyncio
    async def test_get_stats(self, retry_manager):
        """Test getting retry statistics."""
        async def success_func():
            return "success"
        
        await retry_manager.execute_with_retry(
            "test-task-7",
            success_func
        )
        
        stats = await retry_manager.get_stats()
        assert "total_attempts" in stats
        assert "successful_retries" in stats
        assert stats["successful_retries"] >= 1

    @pytest.mark.asyncio
    async def test_clear_record(self, retry_manager):
        """Test clearing retry record."""
        async def success_func():
            return "success"
        
        await retry_manager.execute_with_retry(
            "test-task-8",
            success_func
        )
        
        await retry_manager.clear_record("test-task-8")
        record = await retry_manager.get_record("test-task-8")
        assert record is None


class TestAdaptiveRetryPolicy:
    """Tests for AdaptiveRetryPolicy."""

    def test_default_max_attempts(self):
        """Test default max attempts."""
        policy = AdaptiveRetryPolicy(max_attempts=3)
        assert policy.get_adaptive_max_attempts() == 3

    def test_adaptive_increase_for_network_errors(self):
        """Test adaptive increase for network errors."""
        policy = AdaptiveRetryPolicy(max_attempts=3)
        
        # Simulate network errors
        for _ in range(6):
            policy.record_error("ConnectionTimeout")
        
        assert policy.get_adaptive_max_attempts() == 5  # 3 + 2

    def test_adaptive_delay_increase(self):
        """Test adaptive delay increase."""
        policy = AdaptiveRetryPolicy(initial_delay=1.0)
        
        # Simulate many failures
        for _ in range(11):
            policy.record_error("GenericError")
        
        assert policy.get_adaptive_delay() == 1.5  # 1.0 * 1.5


class TestRetryStrategies:
    """Integration tests for different retry strategies."""

    @pytest.mark.asyncio
    async def test_exponential_strategy(self):
        """Test exponential backoff strategy."""
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=1.0,
            backoff_multiplier=2.0,
            jitter_factor=0.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )
        
        manager = OptimizedRetryManager(policy)
        
        start_time = asyncio.get_event_loop().time()
        
        call_count = 0
        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Fail")
            return "success"
        
        await manager.execute_with_retry("test-exp", fails_twice)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        # Should have delays of 0.1 and 0.2 = 0.3 total
        assert elapsed >= 0.3

    @pytest.mark.asyncio
    async def test_linear_strategy(self):
        """Test linear backoff strategy."""
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=1.0,
            backoff_multiplier=1.0,
            jitter_factor=0.0,
            strategy=RetryStrategy.LINEAR_BACKOFF
        )
        
        manager = OptimizedRetryManager(policy)
        
        call_count = 0
        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Fail")
            return "success"
        
        await manager.execute_with_retry("test-linear", fails_twice)
        assert call_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
