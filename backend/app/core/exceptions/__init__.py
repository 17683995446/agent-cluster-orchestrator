"""
Agent Cluster Orchestrator - Exceptions Package

Provides comprehensive exception handling system for the application.

Key Features:
- Well-structured exception hierarchy
- Clear error codes and messages
- Automatic HTTP response conversion
- Backward compatibility maintained

Usage:
```python
from app.core.exceptions import (
    AgentNotFoundError,
    agent_not_found_error_response
)
```
"""
from app.core.exceptions.base_exceptions import (
    AgentClusterException,
    ResourceNotFoundError,
    AgentNotFoundError,
    TaskNotFoundError,
    LLMProviderError,
    RateLimitExceededError,
    TaskTimeoutError,
    ValidationError,
    ResourceExhaustedError,
    OperationNotAllowedError
)
from app.core.exceptions.http_response_converters import (
    agent_not_found_error_response,
    task_not_found_error_response,
    validation_error_response,
    llm_provider_error_response,
    rate_limit_error_response,
    task_timeout_error_response,
    resource_not_found_error_response,
    resource_exhausted_error_response,
    operation_not_allowed_error_response,
    exception_to_http_response
)

# Backward compatibility aliases
agent_not_found_error = agent_not_found_error_response
task_not_found_error = task_not_found_error_response

__all__ = [
    # Base exceptions
    "AgentClusterException",
    "ResourceNotFoundError",
    # Specific exceptions
    "AgentNotFoundError",
    "TaskNotFoundError",
    "LLMProviderError",
    "RateLimitExceededError",
    "TaskTimeoutError",
    "ValidationError",
    "ResourceExhaustedError",
    "OperationNotAllowedError",
    # HTTP response converters
    "agent_not_found_error_response",
    "task_not_found_error_response",
    "validation_error_response",
    "llm_provider_error_response",
    "rate_limit_error_response",
    "task_timeout_error_response",
    "resource_not_found_error_response",
    "resource_exhausted_error_response",
    "operation_not_allowed_error_response",
    "exception_to_http_response",
    # Backward compatibility
    "agent_not_found_error",
    "task_not_found_error",
]
