from fastapi import HTTPException, status

class AgentClusterException(Exception):
    """Base exception for the application."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)

class AgentNotFoundError(AgentClusterException):
    """Raised when an agent is not found."""
    def __init__(self, agent_id: str):
        super().__init__(
            message=f"Agent with id '{agent_id}' not found",
            code="AGENT_NOT_FOUND"
        )

class TaskNotFoundError(AgentClusterException):
    """Raised when a task is not found."""
    def __init__(self, task_id: str):
        super().__init__(
            message=f"Task with id '{task_id}' not found",
            code="TASK_NOT_FOUND"
        )

class LLMProviderError(AgentClusterException):
    """Raised when an LLM provider fails."""
    def __init__(self, provider: str, reason: str):
        super().__init__(
            message=f"LLM provider '{provider}' failed: {reason}",
            code="LLM_PROVIDER_ERROR"
        )

class RateLimitExceededError(AgentClusterException):
    """Raised when rate limit is exceeded."""
    def __init__(self):
        super().__init__(
            message="Rate limit exceeded",
            code="RATE_LIMIT_EXCEEDED"
        )

class TaskTimeoutError(AgentClusterException):
    """Raised when a task times out."""
    def __init__(self, task_id: str, timeout: int):
        super().__init__(
            message=f"Task '{task_id}' timed out after {timeout} seconds",
            code="TASK_TIMEOUT"
        )

class ValidationError(AgentClusterException):
    """Raised for validation errors."""
    def __init__(self, field: str, message: str):
        super().__init__(
            message=f"Validation error on '{field}': {message}",
            code="VALIDATION_ERROR"
        )

def agent_not_found_error(agent_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "AGENT_NOT_FOUND", "message": f"Agent with id '{agent_id}' not found"}
    )

def task_not_found_error(task_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "TASK_NOT_FOUND", "message": f"Task with id '{task_id}' not found"}
    )

def validation_error_response(field: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"code": "VALIDATION_ERROR", "message": f"Validation error on '{field}': {message}"}
    )
