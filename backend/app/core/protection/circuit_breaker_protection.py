"""
Agent Cluster Orchestrator - Circuit Breaker Protection Module

Implements circuit breaker mechanism with three-state machine for system resilience.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker state enumeration for system protection."""
    CLOSED = "closed"       # Normal state, allows requests
    OPEN = "open"           # Tripped state, rejects all requests
    HALF_OPEN = "half_open" # Recovery state, allows limited requests


@dataclass
class CircuitBreakerConfig:
    """Configuration parameters for circuit breaker behavior."""
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_duration: float = 60.0
    half_open_max_calls: int = 3
    failure_rate_threshold: float = 0.5
    min_call_count: int = 10


class CircuitBreakerError(Exception):
    """Base exception class for circuit breaker related errors."""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Exception raised when circuit breaker is in open state."""
    pass


class CircuitBreaker:
    """
    Complete circuit breaker implementation for system resilience.

    Key Features:
    - Three-state state machine: CLOSED, OPEN, HALF_OPEN
    - Automatic recovery mechanism
    - Failure and success rate statistics
    - Configurable threshold parameters
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.on_state_change = on_state_change
        
        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.total_calls = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        
        # Statistics tracking
        self.call_history: List[Dict[str, Any]] = []
        self.state_changes: List[Dict[str, Any]] = []
        
        logger.info(f"circuit_breaker_initialized", name=name, config=self.config)
    
    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN
    
    async def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Execute function through circuit breaker protection layer.
        
        Args:
            func: Asynchronous function to execute
            *args: Function positional arguments
            fallback: Fallback function for degraded service
            **kwargs: Function keyword arguments
            
        Returns:
            Function execution result
            
        Raises:
            CircuitBreakerOpenError: When circuit breaker is in open state
        """
        if not self._allow_request():
            logger.warning(
                "circuit_breaker_rejected",
                name=self.name,
                state=self.state
            )
            
            if fallback:
                return await fallback(*args, **kwargs)
            
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN"
            )
        
        start_time = time.time()
        self.total_calls += 1
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await self._on_success(time.time() - start_time)
            return result
            
        except Exception as e:
            await self._on_failure(time.time() - start_time, str(e))
            raise
    
    def _allow_request(self) -> bool:
        """Determine if request is allowed based on circuit state."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls < self.config.half_open_max_calls:
                self.half_open_calls += 1
                return True
            return False
        
        return False
    
    def _should_attempt_reset(self) -> bool:
        """Check if it's time to attempt circuit breaker recovery."""
        if self.last_failure_time is None:
            return True
        
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.config.timeout_duration
    
    async def _on_success(self, duration: float):
        """Handle successful function call event."""
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.config.success_threshold:
                logger.info(
                    "circuit_breaker_recovered",
                    name=self.name,
                    half_open_successes=self.success_count
                )
                self._transition_to(CircuitState.CLOSED)
        
        self._record_call(success=True, duration=duration)
    
    async def _on_failure(self, duration: float, error: str):
        """Handle failed function call event."""
        self.failure_count += 1
        self.success_count = 0
        self.last_failure_time = time.time()
        
        self._record_call(success=False, duration=duration, error=error)
        
        if self.state == CircuitState.HALF_OPEN:
            logger.warning(
                "circuit_breaker_reopened",
                name=self.name,
                half_open_calls=self.half_open_calls
            )
            self._transition_to(CircuitState.OPEN)
            
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                logger.error(
                    "circuit_breaker_opened",
                    name=self.name,
                    failure_count=self.failure_count
                )
                self._transition_to(CircuitState.OPEN)
    
    def _transition_to(self, new_state: CircuitState):
        """Handle circuit breaker state transition logic."""
        old_state = self.state
        self.state = new_state
        
        if new_state == CircuitState.HALF_OPEN:
            self.half_open_calls = 0
            self.success_count = 0
        elif new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
        
        self.state_changes.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        if self.on_state_change:
            try:
                self.on_state_change(old_state, new_state)
            except Exception as e:
                logger.error(f"state_change_callback_error: {e}")
        
        logger.info(
            "circuit_breaker_state_changed",
            name=self.name,
            from_state=old_state.value,
            to_state=new_state.value
        )
    
    def _record_call(self, success: bool, duration: float, error: Optional[str] = None):
        """Record circuit breaker call event for monitoring."""
        self.call_history.append({
            "success": success,
            "duration": duration,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": self.state.value
        })
        
        if len(self.call_history) > 1000:
            self.call_history = self.call_history[-1000:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive circuit breaker statistics."""
        recent_calls = self.call_history[-self.config.min_call_count:]
        
        if not recent_calls:
            return {
                "name": self.name,
                "state": self.state.value,
                "total_calls": self.total_calls,
                "failure_count": self.failure_count,
                "success_count": self.success_count
            }
        
        recent_success = sum(1 for c in recent_calls if c["success"])
        recent_failure = len(recent_calls) - recent_success
        failure_rate = recent_failure / len(recent_calls)
        
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "recent_calls": len(recent_calls),
            "recent_success": recent_success,
            "recent_failure": recent_failure,
            "recent_failure_rate": failure_rate,
            "last_failure_time": self.last_failure_time,
            "state_changes": len(self.state_changes)
        }
    
    def reset(self):
        """Reset circuit breaker to initial closed state."""
        self._transition_to(CircuitState.CLOSED)
        self.call_history.clear()
        self.state_changes.clear()
        logger.info("circuit_breaker_reset", name=self.name)


class CircuitBreakerManager:
    """
    Manager class for multiple circuit breaker instances.
    
    Provides centralized management and monitoring for all circuit breakers.
    """
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
        logger.info("circuit_breaker_manager_initialized")
    
    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker instance."""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name, config)
        
        return self.breakers[name]
    
    async def call(
        self,
        breaker_name: str,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """Execute function through specified circuit breaker."""
        breaker = self.get_or_create(breaker_name)
        return await breaker.call(func, *args, fallback=fallback, **kwargs)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all registered circuit breakers."""
        return {
            name: breaker.get_stats()
            for name, breaker in self.breakers.items()
        }
    
    def reset_all(self):
        """Reset all registered circuit breakers."""
        for breaker in self.breakers.values():
            breaker.reset()
