"""
Agent Cluster Orchestrator - HTTP Exception Response Module

Provides utilities to convert application exceptions to HTTP responses.
"""
from __future__ import annotations

from fastapi import HTTPException, status

from app.core.exceptions.base_exceptions import (
    AgentNotFoundError,
    TaskNotFoundError,
    ValidationError,
    LLMProviderError,
    RateLimitExceededError,
    TaskTimeoutError,
    ResourceNotFoundError,
    ResourceExhaustedError,
    OperationNotAllowedError
)


def agent_not_found_error_response(agent_id: str) -> HTTPException:
    """Create HTTP 404 response for agent not found error."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "AGENT_NOT_FOUND",
            "message": f"Agent with id '{agent_id}' not found"
        }
    )


def task_not_found_error_response(task_id: str) -> HTTPException:
    """Create HTTP 404 response for task not found error."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "TASK_NOT_FOUND",
            "message": f"Task with id '{task_id}' not found"
        }
    )


def validation_error_response(field: str, message: str) -> HTTPException:
    """Create HTTP 422 response for validation errors."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "VALIDATION_ERROR",
            "message": f"Validation error on '{field}': {message}"
        }
    )


def llm_provider_error_response(provider: str, reason: str) -> HTTPException:
    """Create HTTP 500 response for LLM provider errors."""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "code": "LLM_PROVIDER_ERROR",
            "message": f"LLM provider '{provider}' failed: {reason}"
        }
    )


def rate_limit_error_response() -> HTTPException:
    """Create HTTP 429 response for rate limit errors."""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "Rate limit exceeded"
        }
    )


def task_timeout_error_response(task_id: str, timeout: int) -> HTTPException:
    """Create HTTP 408 response for task timeout errors."""
    return HTTPException(
        status_code=status.HTTP_408_REQUEST_TIMEOUT,
        detail={
            "code": "TASK_TIMEOUT",
            "message": f"Task '{task_id}' timed out after {timeout} seconds"
        }
    )


def resource_not_found_error_response(resource_type: str, resource_id: str) -> HTTPException:
    """Create HTTP 404 response for generic resource not found errors."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": f"{resource_type.upper()}_NOT_FOUND",
            "message": f"{resource_type} with id '{resource_id}' not found"
        }
    )


def resource_exhausted_error_response(resource: str, message: str) -> HTTPException:
    """Create HTTP 503 response for resource exhaustion errors."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "RESOURCE_EXHAUSTED",
            "message": f"Resource '{resource}' exhausted: {message}"
        }
    )


def operation_not_allowed_error_response(operation: str, reason: str) -> HTTPException:
    """Create HTTP 403 response for operation not allowed errors."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "OPERATION_NOT_ALLOWED",
            "message": f"Operation '{operation}' not allowed: {reason}"
        }
    )


def exception_to_http_response(exception: Exception) -> HTTPException:
    """
    Convert application exception to appropriate HTTP response.
    
    Args:
        exception: Application exception instance
        
    Returns:
        HTTPException with appropriate status code and message
    """
    if isinstance(exception, AgentNotFoundError):
        return agent_not_found_error_response(exception.message.split("'")[1])
    elif isinstance(exception, TaskNotFoundError):
        return task_not_found_error_response(exception.message.split("'")[1])
    elif isinstance(exception, ValidationError):
        # Extract field from error message
        field = exception.message.split("'")[1]
        return validation_error_response(field, exception.message.split(": ")[1])
    elif isinstance(exception, LLMProviderError):
        provider = exception.message.split("'")[1]
        reason = exception.message.split(": ")[1]
        return llm_provider_error_response(provider, reason)
    elif isinstance(exception, RateLimitExceededError):
        return rate_limit_error_response()
    elif isinstance(exception, TaskTimeoutError):
        # Extract task_id and timeout from message
        task_id = exception.message.split("'")[1]
        timeout = int(exception.message.split("after ")[1].split(" ")[0])
        return task_timeout_error_response(task_id, timeout)
    elif isinstance(exception, ResourceNotFoundError):
        # Parse message to extract resource type and id
        parts = exception.message.split(" with id '")
        resource_type = parts[0]
        resource_id = parts[1].rstrip("'")
        return resource_not_found_error_response(resource_type, resource_id)
    elif isinstance(exception, ResourceExhaustedError):
        # Parse message to extract resource and message
        resource = exception.message.split("'")[1]
        msg = exception.message.split(": ")[1]
        return resource_exhausted_error_response(resource, msg)
    elif isinstance(exception, OperationNotAllowedError):
        # Parse message to extract operation and reason
        operation = exception.message.split("'")[1]
        reason = exception.message.split(": ")[1]
        return operation_not_allowed_error_response(operation, reason)
    else:
        # Default to 500 Internal Server Error
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": str(exception)
            }
        )
