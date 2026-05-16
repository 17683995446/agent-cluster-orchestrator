"""
Optimized Task Retry Manager
Advanced retry system with intelligent backoff strategies.
"""
from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

import structlog

logger = structlog.get_logger()


class RetryStrategy(Enum):
    """Retry strategies with intelligent backoff."""
    EXPONENTIAL_BACKOFF = auto()
    LINEAR_BACKOFF = auto()
    FIXED_DELAY = auto()
    RANDOM_DELAY = auto()
    FIBONACCI_BACKOFF = auto()
    DECORRELATED_JITTER = auto()
    CIRCUIT_BREAKER = auto()


class RetryStatus(Enum):
    """Status of a retry attempt."""
    PENDING = auto()
    IN_PROGRESS = auto()
    SUCCESS = auto()
    FAILED = auto()
    ABANDONED = auto()
    CIRCUIT_OPEN = auto()


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


@dataclass
class RetryPolicy:
    """Optimized configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 0.5
    max_delay: float = 10.0
    backoff_multiplier: float = 1.5
    jitter_factor: float = 0.2
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    retry_on_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 3
    circuit_breaker_reset_timeout: float = 30.0
    timeout_per_attempt: float = 5.0


@dataclass
class RetryAttempt:
    """Single retry attempt record."""
    attempt: int
    timestamp: float
    error: Optional[Exception] = None
    duration: Optional[float] = None
    success: bool = False


@dataclass
class RetryRecord:
    """Complete retry record for a task."""
    task_id: str
    policy: RetryPolicy
    status: RetryStatus = RetryStatus.PENDING
    attempts: List[RetryAttempt] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_open_since: Optional[float] = None
    total_failures: int = 0
    last_success_at: Optional[float] = None


class BackoffCalculator:
    """Calculate backoff delays with various strategies."""
    
    @staticmethod
    def exponential(
        attempt: int,
        initial_delay: float,
        max_delay: float,
        multiplier: float,
        jitter_factor: float
    ) -> float:
        """Calculate exponential backoff delay."""
        delay = initial_delay * (multiplier ** attempt)
        delay = min(delay, max_delay)
        
        if jitter_factor > 0:
            jitter = delay * jitter_factor * (random.random() * 2 - 1)
            delay = delay + jitter
        
        return max(0, delay)
    
    @staticmethod
    def linear(
        attempt: int,
        initial_delay: float,
        max_delay: float,
        multiplier: float,
        jitter_factor: float
    ) -> float:
        """Calculate linear backoff delay."""
        delay = initial_delay + (attempt * initial_delay * multiplier)
        delay = min(delay, max_delay)
        
        if jitter_factor > 0:
            jitter = delay * jitter_factor * (random.random() * 2 - 1)
            delay = delay + jitter
        
        return max(0, delay)
    
    @staticmethod
    def fibonacci(
        attempt: int,
        initial_delay: float,
        max_delay: float,
        multiplier: float,
        jitter_factor: float
    ) -> float:
        """Calculate Fibonacci-based backoff delay."""
        fib = [0, 1]
        for i in range(2, attempt + 2):
            fib.append(fib[i-1] + fib[i-2])
        
        delay = initial_delay * fib[min(attempt + 1, len(fib) - 1)]
        delay = min(delay, max_delay)
        
        if jitter_factor > 0:
            jitter = delay * jitter_factor * (random.random() * 2 - 1)
            delay = delay + jitter
        
        return max(0, delay)
    
    @staticmethod
    def decorrelated_jitter(
        attempt: int,
        initial_delay: float,
        max_delay: float,
        multiplier: float,
        jitter_factor: float,
        previous_delay: float = 0
    ) -> float:
        """Calculate decorrelated jitter backoff."""
        if previous_delay == 0:
            delay = initial_delay * multiplier * random.random()
        else:
            delay = min(previous_delay * multiplier * random.random(), max_delay)
        
        delay = min(delay, max_delay)
        
        if jitter_factor > 0:
            jitter = delay * jitter_factor * (random.random() * 2 - 1)
            delay = delay + jitter
        
        return max(0, delay)
    
    @classmethod
    def calculate(
        cls,
        strategy: RetryStrategy,
        attempt: int,
        policy: RetryPolicy,
        previous_delay: float = 0
    ) -> float:
        """Calculate delay based on strategy."""
        calculators = {
            RetryStrategy.EXPONENTIAL_BACKOFF: cls.exponential,
            RetryStrategy.LINEAR_BACKOFF: cls.linear,
            RetryStrategy.FIBONACCI_BACKOFF: cls.fibonacci,
            RetryStrategy.DECORRELATED_JITTER: cls.decorrelated_jitter,
            RetryStrategy.FIXED_DELAY: lambda *args, **kwargs: policy.initial_delay,
            RetryStrategy.RANDOM_DELAY: lambda *args, **kwargs: random.uniform(
                policy.initial_delay, policy.max_delay
            ),
        }
        
        calculator = calculators.get(strategy, cls.exponential)
        
        if strategy == RetryStrategy.DECORRELATED_JITTER:
            return calculator(
                attempt,
                policy.initial_delay,
                policy.max_delay,
                policy.backoff_multiplier,
                policy.jitter_factor,
                previous_delay
            )
        
        return calculator(
            attempt,
            policy.initial_delay,
            policy.max_delay,
            policy.backoff_multiplier,
            policy.jitter_factor
        )


class CircuitBreaker:
    """Circuit breaker implementation for retry management."""
    
    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout: float = 30.0,
        half_open_requests: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_requests = half_open_requests
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_successes = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
    
    async def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    elapsed = datetime.now().timestamp() - self._last_failure_time
                    if elapsed >= self.reset_timeout:
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_successes = 0
                        logger.info("circuit_breaker_half_open")
                        return False
                return True
            return False
    
    async def record_success(self):
        """Record a successful attempt."""
        async with self._lock:
            self._failure_count = 0
            self._last_failure_time = None
            
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.half_open_requests:
                    self._state = CircuitState.CLOSED
                    self._half_open_successes = 0
                    logger.info("circuit_breaker_closed")
    
    async def record_failure(self):
        """Record a failed attempt."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now().timestamp()
            
            if self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "circuit_breaker_opened",
                        failure_count=self._failure_count
                    )
    
    async def get_state(self) -> CircuitState:
        """Get current circuit state with timeout check."""
        async with self._lock:
            if self._state == CircuitState.OPEN and self._last_failure_time:
                elapsed = datetime.now().timestamp() - self._last_failure_time
                if elapsed >= self.reset_timeout:
                    return CircuitState.HALF_OPEN
            return self._state


class OptimizedRetryManager:
    """
    Optimized retry manager with advanced features.
    
    Key improvements:
    1. Multiple backoff strategies
    2. Circuit breaker integration
    3. Adaptive retry based on error types
    4. Better statistics tracking
    5. Configurable timeouts per attempt
    """
    
    def __init__(self, default_policy: Optional[RetryPolicy] = None):
        self.default_policy = default_policy or RetryPolicy()
        self._retry_records: Dict[str, RetryRecord] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
        self._stats = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "circuit_breaker_trips": 0
        }
    
    async def execute_with_retry(
        self,
        task_id: str,
        func: Callable[..., Any],
        policy: Optional[RetryPolicy] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with optimized retry logic.
        
        Args:
            task_id: Unique task identifier
            func: Async function to execute
            policy: Custom retry policy (uses default if None)
            *args, **kwargs: Arguments to pass to func
        
        Returns:
            Result from successful execution
        
        Raises:
            Exception: If all retry attempts fail
        """
        policy = policy or self.default_policy
        record = await self._get_or_create_record(task_id, policy)
        
        circuit_breaker = await self._get_circuit_breaker(task_id, policy)
        
        if await circuit_breaker.is_open():
            logger.warning(
                "circuit_breaker_rejecting",
                task_id=task_id,
                circuit_state=circuit_breaker.state
            )
            raise Exception(f"Circuit breaker open for task {task_id}")
        
        last_error: Optional[Exception] = None
        last_delay = 0.0
        
        for attempt in range(policy.max_attempts):
            start_time = datetime.now().timestamp()
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=policy.timeout_per_attempt
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(func, *args, **kwargs),
                        timeout=policy.timeout_per_attempt
                    )
                
                duration = datetime.now().timestamp() - start_time
                attempt_record = RetryAttempt(
                    attempt=attempt + 1,
                    timestamp=start_time,
                    duration=duration,
                    success=True
                )
                record.attempts.append(attempt_record)
                record.status = RetryStatus.SUCCESS
                record.total_failures = 0
                record.last_success_at = start_time
                
                await circuit_breaker.record_success()
                self._stats["successful_retries"] += 1
                self._stats["total_attempts"] += 1
                
                logger.info(
                    "retry_succeeded",
                    task_id=task_id,
                    attempt=attempt + 1,
                    duration=duration
                )
                
                return result
                
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(
                    "retry_timeout",
                    task_id=task_id,
                    attempt=attempt + 1,
                    timeout=policy.timeout_per_attempt
                )
                
            except Exception as e:
                last_error = e
                should_retry = self._should_retry(e, policy)
                
                if not should_retry:
                    logger.info(
                        "retry_not_worthwhile",
                        task_id=task_id,
                        error=str(e)
                    )
                    break
                
                logger.warning(
                    "retry_attempt_failed",
                    task_id=task_id,
                    attempt=attempt + 1,
                    error=str(e),
                    error_type=type(e).__name__
                )
            
            await circuit_breaker.record_failure()
            attempt_record = RetryAttempt(
                attempt=attempt + 1,
                timestamp=start_time,
                error=last_error,
                duration=datetime.now().timestamp() - start_time,
                success=False
            )
            record.attempts.append(attempt_record)
            record.total_failures += 1
            
            if attempt < policy.max_attempts - 1:
                delay = BackoffCalculator.calculate(
                    policy.strategy,
                    attempt,
                    policy,
                    last_delay
                )
                last_delay = delay
                
                logger.debug(
                    "retry_backing_off",
                    task_id=task_id,
                    delay=delay,
                    next_attempt=attempt + 2
                )
                
                await asyncio.sleep(delay)
        
        record.status = RetryStatus.FAILED
        self._stats["failed_retries"] += 1
        self._stats["total_attempts"] += 1
        
        if last_error:
            raise last_error
        raise Exception(f"All {policy.max_attempts} retry attempts failed for task {task_id}")
    
    def _should_retry(self, error: Exception, policy: RetryPolicy) -> bool:
        """Determine if an error should trigger a retry."""
        if not policy.retry_on_exceptions:
            return True
        
        return isinstance(error, policy.retry_on_exceptions)
    
    async def _get_or_create_record(
        self,
        task_id: str,
        policy: RetryPolicy
    ) -> RetryRecord:
        """Get or create retry record for task."""
        async with self._lock:
            if task_id not in self._retry_records:
                self._retry_records[task_id] = RetryRecord(
                    task_id=task_id,
                    policy=policy
                )
            return self._retry_records[task_id]
    
    async def _get_circuit_breaker(
        self,
        task_id: str,
        policy: RetryPolicy
    ) -> CircuitBreaker:
        """Get or create circuit breaker for task."""
        async with self._lock:
            if task_id not in self._circuit_breakers:
                self._circuit_breakers[task_id] = CircuitBreaker(
                    failure_threshold=policy.circuit_breaker_threshold,
                    reset_timeout=policy.circuit_breaker_reset_timeout
                )
            return self._circuit_breakers[task_id]
    
    async def get_record(self, task_id: str) -> Optional[RetryRecord]:
        """Get retry record for task."""
        return self._retry_records.get(task_id)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get retry statistics."""
        return {
            **self._stats,
            "success_rate": (
                self._stats["successful_retries"] / self._stats["total_attempts"]
                if self._stats["total_attempts"] > 0
                else 0.0
            )
        }
    
    async def clear_record(self, task_id: str):
        """Clear retry record for task."""
        async with self._lock:
            self._retry_records.pop(task_id, None)
            self._circuit_breakers.pop(task_id, None)


class AdaptiveRetryPolicy(RetryPolicy):
    """Retry policy that adapts based on error patterns."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._error_history: Dict[str, int] = {}
        self._adaptivity_enabled = True
    
    def record_error(self, error_type: str):
        """Record an error type for adaptive adjustment."""
        if error_type in self._error_history:
            self._error_history[error_type] += 1
        else:
            self._error_history[error_type] = 1
    
    def get_adaptive_max_attempts(self) -> int:
        """Get adjusted max attempts based on error history."""
        if not self._adaptivity_enabled:
            return self.max_attempts
        
        network_errors = sum(
            count for error, count in self._error_history.items()
            if 'timeout' in error.lower() or 'connection' in error.lower()
        )
        
        if network_errors > 5:
            return min(self.max_attempts + 2, 10)
        
        return self.max_attempts
    
    def get_adaptive_delay(self) -> float:
        """Get adjusted initial delay based on error history."""
        if not self._adaptivity_enabled:
            return self.initial_delay
        
        recent_failures = sum(self._error_history.values())
        
        if recent_failures > 10:
            return min(self.initial_delay * 1.5, self.max_delay)
        
        return self.initial_delay


def optimized_retry(
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 10.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
):
    """
    Decorator for adding optimized retry logic to async functions.
    
    Usage:
        @optimized_retry(max_attempts=3, initial_delay=1.0)
        async def my_function():
            pass
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            policy = RetryPolicy(
                max_attempts=max_attempts,
                initial_delay=initial_delay,
                max_delay=max_delay,
                strategy=strategy
            )
            manager = OptimizedRetryManager(policy)
            return await manager.execute_with_retry(
                f"{func.__name__}_{id(func)}",
                func,
                policy,
                *args,
                **kwargs
            )
        return wrapper
    return decorator
