"""
Agent Cluster Orchestrator - Protection Mechanisms Package

Provides comprehensive system protection mechanisms including:
- Circuit breaker for fault tolerance
- Connection pooling for resource management
- Timeout protection for task execution
- Adaptive queue for backpressure control

This package maintains backward compatibility while improving modularity.
"""
from app.core.protection.circuit_breaker_protection import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerManager,
    CircuitBreakerOpenError,
    CircuitState
)
from app.core.protection.connection_pool_management import (
    ConnectionPool,
    ConnectionWrapper,
    PoolConfig,
    PoolExhaustedError
)
from app.core.protection.timeout_protection import (
    TimeoutConfig,
    TimeoutError,
    TimeoutMonitor,
    execute_with_timeout
)
from app.core.protection.adaptive_queue_management import (
    AdaptiveQueue,
    PriorityItem,
    QueueConfig,
    QueueFullError
)

# Global instances for backward compatibility
_circuit_breaker_manager: Optional[CircuitBreakerManager] = None
_timeout_monitor: Optional[TimeoutMonitor] = None


def initialize_protection_system() -> None:
    """Initialize protection system with default configurations."""
    global _circuit_breaker_manager, _timeout_monitor
    
    _circuit_breaker_manager = CircuitBreakerManager()
    _timeout_monitor = TimeoutMonitor()


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get or create circuit breaker manager instance."""
    global _circuit_breaker_manager
    
    if not _circuit_breaker_manager:
        initialize_protection_system()
    
    return _circuit_breaker_manager


def get_timeout_monitor() -> TimeoutMonitor:
    """Get or create timeout monitor instance."""
    global _timeout_monitor
    
    if not _timeout_monitor:
        initialize_protection_system()
    
    return _timeout_monitor


__all__ = [
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerManager",
    "CircuitBreakerOpenError",
    "CircuitState",
    # Connection Pool
    "ConnectionPool",
    "ConnectionWrapper",
    "PoolConfig",
    "PoolExhaustedError",
    # Timeout Protection
    "TimeoutConfig",
    "TimeoutError",
    "TimeoutMonitor",
    "execute_with_timeout",
    # Adaptive Queue
    "AdaptiveQueue",
    "PriorityItem",
    "QueueConfig",
    "QueueFullError",
    # System Initialization
    "initialize_protection_system",
    "get_circuit_breaker_manager",
    "get_timeout_monitor",
]
