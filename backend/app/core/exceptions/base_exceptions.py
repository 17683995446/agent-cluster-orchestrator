"""
Agent Cluster Orchestrator - Base Exceptions Module

Provides core exception classes and error handling utilities.
"""
from __future__ import annotations


class AgentClusterException(Exception):
    """Base exception class for all application-level errors."""
    
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ResourceNotFoundError(AgentClusterException):
    """Base exception for resource not found errors."""
    
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} with id '{resource_id}' not found",
            code=f"{resource_type.upper()}_NOT_FOUND"
        )


class AgentNotFoundError(ResourceNotFoundError):
    """Raised when an agent resource cannot be located."""
    
    def __init__(self, agent_id: str):
        super().__init__("Agent", agent_id)


class TaskNotFoundError(ResourceNotFoundError):
    """Raised when a task resource cannot be located."""
    
    def __init__(self, task_id: str):
        super().__init__("Task", task_id)


class LLMProviderError(AgentClusterException):
    """Raised when an LLM provider encounters an error."""
    
    def __init__(self, provider: str, reason: str):
        super().__init__(
            message=f"LLM provider '{provider}' failed: {reason}",
            code="LLM_PROVIDER_ERROR"
        )


class RateLimitExceededError(AgentClusterException):
    """Raised when API rate limits have been exceeded."""
    
    def __init__(self):
        super().__init__(
            message="Rate limit exceeded",
            code="RATE_LIMIT_EXCEEDED"
        )


class TaskTimeoutError(AgentClusterException):
    """Raised when task execution exceeds timeout duration."""
    
    def __init__(self, task_id: str, timeout: int):
        super().__init__(
            message=f"Task '{task_id}' timed out after {timeout} seconds",
            code="TASK_TIMEOUT"
        )


class ValidationError(AgentClusterException):
    """Raised when input or configuration validation fails."""
    
    def __init__(self, field: str, message: str):
        super().__init__(
            message=f"Validation error on '{field}': {message}",
            code="VALIDATION_ERROR"
        )


class ResourceExhaustedError(AgentClusterException):
    """Raised when system resources are exhausted."""
    
    def __init__(self, resource: str, message: str):
        super().__init__(
            message=f"Resource '{resource}' exhausted: {message}",
            code="RESOURCE_EXHAUSTED"
        )


class OperationNotAllowedError(AgentClusterException):
    """Raised when an operation is not permitted."""
    
    def __init__(self, operation: str, reason: str):
        super().__init__(
            message=f"Operation '{operation}' not allowed: {reason}",
            code="OPERATION_NOT_ALLOWED"
        )
