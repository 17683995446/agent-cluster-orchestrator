from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
from typing import Union, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger()


class AgentClusterException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Dict[str, Any] = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ResourceNotFoundException(AgentClusterException):
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=f"{resource_type} with id '{resource_id}' not found",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id}
        )


class ResourceAlreadyExistsException(AgentClusterException):
    def __init__(self, resource_type: str, identifier: str):
        super().__init__(
            code="RESOURCE_ALREADY_EXISTS",
            message=f"{resource_type} '{identifier}' already exists",
            status_code=409,
            details={"resource_type": resource_type, "identifier": identifier}
        )


class AuthenticationException(AgentClusterException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            code="AUTHENTICATION_FAILED",
            message=message,
            status_code=401
        )


class AuthorizationException(AgentClusterException):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            code="INSUFFICIENT_PERMISSIONS",
            message=message,
            status_code=403
        )


class RateLimitExceededException(AgentClusterException):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many requests. Please try again later.",
            status_code=429,
            details={"retry_after": retry_after}
        )


class CircuitBreakerOpenException(AgentClusterException):
    def __init__(self, service_name: str):
        super().__init__(
            code="CIRCUIT_BREAKER_OPEN",
            message=f"Circuit breaker is open for service '{service_name}'",
            status_code=503,
            details={"service_name": service_name}
        )


class LLMProviderException(AgentClusterException):
    def __init__(self, provider: str, message: str):
        super().__init__(
            code="LLM_PROVIDER_ERROR",
            message=f"LLM provider '{provider}' error: {message}",
            status_code=502,
            details={"provider": provider}
        )


class TaskExecutionException(AgentClusterException):
    def __init__(self, task_id: str, message: str):
        super().__init__(
            code="TASK_EXECUTION_ERROR",
            message=f"Task '{task_id}' execution failed: {message}",
            status_code=500,
            details={"task_id": task_id}
        )


class DatabaseException(AgentClusterException):
    def __init__(self, operation: str, message: str):
        super().__init__(
            code="DATABASE_ERROR",
            message=f"Database operation '{operation}' failed: {message}",
            status_code=500,
            details={"operation": operation}
        )


async def agent_cluster_exception_handler(request: Request, exc: AgentClusterException):
    logger.error(
        "agent_cluster_exception",
        code=exc.code,
        message=exc.message,
        path=request.url.path,
        method=request.method,
        details=exc.details,
        timestamp=datetime.utcnow().isoformat()
    )
    
    content = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path)
        }
    }
    
    if exc.status_code == 429 and exc.details.get("retry_after"):
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers={"Retry-After": str(exc.details["retry_after"])}
        )
    
    return JSONResponse(status_code=exc.status_code, content=content)


async def validation_exception_handler(request: Request, exc: Union[RequestValidationError, ValidationError]):
    errors = []
    if isinstance(exc, RequestValidationError):
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })
    else:
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })
    
    logger.warning(
        "validation_error",
        path=request.url.path,
        method=request.method,
        errors=errors,
        timestamp=datetime.utcnow().isoformat()
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors},
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            }
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning(
        "http_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method,
        timestamp=datetime.utcnow().isoformat()
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            }
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        error_type=type(exc).__name__,
        error=str(exc),
        path=request.url.path,
        method=request.method,
        exc_info=True,
        timestamp=datetime.utcnow().isoformat()
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Our team has been notified.",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url.path)
            }
        }
    )


def register_exception_handlers(app):
    from fastapi import FastAPI
    app.add_exception_handler(AgentClusterException, agent_cluster_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
