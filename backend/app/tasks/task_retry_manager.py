"""
Task Retry Manager with Exponential Backoff
Robust task retry system with configurable strategies.
"""
from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, Type
import structlog

logger = structlog.get_logger()


class RetryStrategy(Enum):
    """Retry strategies."""
    EXPONENTIAL_BACKOFF = auto()
    LINEAR_BACKOFF = auto()
    FIXED_DELAY = auto()
    RANDOM_DELAY = auto()
    CIRCUITS_BREAKER = auto()


class RetryStatus(Enum):
    """Status of a retry attempt."""
    PENDING = auto()
    IN_PROGRESS = auto()
    SUCCESS = auto()
    FAILED = auto()
    ABANDONED = auto()


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 5
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    retry_on_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    circuit_breaker_threshold: int = 3
    circuit_breaker_reset_timeout: float = 60.0


@dataclass
class RetryAttempt:
    """Single retry attempt record."""
    attempt: int
    timestamp: float
    error: Optional[Exception] = None
    duration: Optional[float] = None


@dataclass
class RetryRecord:
    """Complete retry record for a task."""
    task_id: str
    policy: RetryPolicy
    status: RetryStatus = RetryStatus.PENDING
    attempts: List[RetryAttempt] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    circuit_open_since: Optional[float] = None
    total_failures: int = 0


class RetryManager:
    """
    Retry manager that manages retry logic for tasks.
    
    Features:
    - Multiple retry strategies
    - Circuit breaker pattern
    - Jitter support
    - Statistics tracking
    """
    
    def __init__(self, default_policy: Optional[RetryPolicy] = None):
        self.default_policy = default_policy or RetryPolicy()
        self._retry_records: Dict[str, RetryRecord] = {}
        self._circuit_breakers: Dict[str, int] = {}
    
    async def execute_with_retry(
        self,
        task_id: str,
        func: Callable[[], Any],
        policy: Optional[RetryPolicy] = None,
    ):
        """
        Execute a function with retry logic.
        
        Args:
            task_id: Unique identifier for the task
        func: The async function to execute
        policy: Optional custom retry policy
        
        Returns:
            The result of the function
        
        Raises:
            The last exception if all retries fail
        """
        policy = policy or self.default_policy
        
        if task_id not in self._retry_records:
            self._retry_records[task_id] = RetryRecord(
                task_id=task_id,
                policy=policy,
                status=RetryStatus.PENDING,
            )
        
        record = self._retry_records[task_id]
        record.status = RetryStatus.IN_PROGRESS
        
        last_exception = None
        
        for attempt in range(1, policy.max_attempts + 1):
            start_time = datetime.now().timestamp()
            
            try:
                logger.debug(
                    "retry_attempt_started",
                    task_id=task_id,
                    attempt=attempt,
                )
                
                result = await func()
                
                attempt_duration = datetime.now().timestamp() - start_time
                
                record.attempts.append(
                    RetryAttempt(
                        attempt=attempt,
                        timestamp=start_time,
                        duration=attempt_duration,
                    )
                )
                record.status = RetryStatus.SUCCESS
                
                logger.debug(
                    "retry_attempt_succeeded",
                    task_id=task_id,
                    attempt=attempt,
                    duration_ms=int(attempt_duration * 1000),
                )
                
                return result
                
            except policy.retry_on_exceptions as e:
                last_exception = e
                attempt_duration = datetime.now().timestamp() - start_time
                
                record.attempts.append(
                    RetryAttempt(
                        attempt=attempt,
                        timestamp=start_time,
                        error=e,
                        duration=attempt_duration,
                    )
                )
                record.total_failures += 1
                
                logger.warning(
                    "retry_attempt_failed",
                    task_id=task_id,
                    attempt=attempt,
                    error=str(e),
                    duration_ms=int(attempt_duration * 1000),
                )
                
                if attempt >= policy.max_attempts:
                    break
                
                delay = self._calculate_delay(attempt, policy)
                
                logger.debug(
                    "waiting_before_retry",
                    task_id=task_id,
                    attempt=attempt,
                    delay_seconds=delay,
                )
                
                await asyncio.sleep(delay)
        
        record.status = RetryStatus.FAILED
        logger.error(
            "retry_all_attempts_failed",
            task_id=task_id,
            total_attempts=len(record.attempts),
            last_error=str(last_exception),
        )
        
        raise last_exception
    
    def _calculate_delay(self, attempt: int, policy: RetryPolicy) -> float:
        """Calculate delay for next attempt."""
        if policy.strategy == RetryStrategy.FIXED_DELAY:
            delay = policy.initial_delay
        
        elif policy.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = policy.initial_delay * attempt
        
        elif policy.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = policy.initial_delay * (policy.backoff_multiplier ** (attempt - 1))
            delay = min(delay, policy.max_delay)
        
        elif policy.strategy == RetryStrategy.RANDOM_DELAY:
            delay = random.uniform(policy.initial_delay, policy.max_delay)
        
        else:
            delay = policy.initial_delay
        
        if policy.jitter_factor > 0:
            jitter = random.uniform(1 - policy.jitter_factor, 1 + policy.jitter_factor)
            delay *= jitter
        
        return min(delay, policy.max_delay)
        
        return delay
    
    async def with_circuit_breaker(
        self,
        circuit_id: str,
        func: Callable[[], Any],
        policy: Optional[RetryPolicy] = None,
    ):
        """
        Execute with circuit breaker protection.
        
        If the function fails threshold times, the circuit opens and further calls are rejected.
        """
        policy = policy or self.default_policy
        
        if self._is_circuit_open(circuit_id, policy):
            raise Exception(f"Circuit breaker open for {circuit_id}")
        
        try:
            result = await func()
            self._reset_circuit(circuit_id)
            return result
        except Exception as e:
            self._record_circuit_failure(circuit_id)
            raise
    
    def _is_circuit_open(self, circuit_id: str, policy: RetryPolicy) -> bool:
        """Check if circuit is open."""
        if circuit_id not in self._circuit_breakers:
            return False
        
        failure_count, open_since = self._circuit_breakers[circuit_id]
        
        if failure_count < policy.circuit_breaker_threshold:
            return False
        
        if open_since is None:
            return True
        
        reset_time = open_since + policy.circuit_breaker_reset_timeout
        if datetime.now().timestamp() > reset_time:
            self._reset_circuit(circuit_id)
            return False
        
        return True
    
    def _record_circuit_failure(self, circuit_id: str) -> None:
        if circuit_id not in self._circuit_breakers:
            self._circuit_breakers[circuit_id] = (0, datetime.now().timestamp())
        
        current_count, _ = self._circuit_breakers[circuit_id]
        self._circuit_breakers[circuit_id] = (
            current_count + 1, datetime.now().timestamp())
    
    def _reset_circuit(self, circuit_id: str) -> None:
        if circuit_id in self._circuit_breakers:
            del self._circuit_breakers[circuit_id]
    
    def get_retry_status(self, task_id: str) -> Optional[RetryRecord]:
        """Get retry record for a task."""
        return self._retry_records.get(task_id)
    
    def clear_retry_records(self, task_id: Optional[str] = None) -> None:
        if task_id:
            if task_id in self._retry_records:
                del self._retry_records[task_id]
        else:
            self._retry_records.clear()


# Convenience decorator
def retry(
    policy: Optional[RetryPolicy] = None,
):
    """
    Decorator for async functions to add retry logic.
    """
    manager = RetryManager(default_policy=policy)
    
    def decorator(func):
        async def wrapper(task_id: str, *args, **kwargs):
            async def do_call():
                return await func(*args, **kwargs)
            
            return await manager.execute_with_retry(task_id, do_call, policy)
        return wrapper
    return decorator


# Default retry policies
DEFAULT_POLICY = RetryPolicy()
AGGRESSIVE_POLICY = RetryPolicy(
    max_attempts=10,
    initial_delay=0.5,
    max_delay=30.0,
)
CONSERVATIVE_POLICY = RetryPolicy(
    max_attempts=3,
    initial_delay=5.0,
    max_delay=120.0,
)


# Global instance
retry_manager = RetryManager()
