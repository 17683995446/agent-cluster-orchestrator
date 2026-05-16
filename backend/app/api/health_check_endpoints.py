from fastapi import APIRouter, Response
from pydantic import BaseModel
from typing import Dict, Any
import time
import psutil
from app.application_configuration import settings

router = APIRouter(tags=["Health"])

class HealthResponse(BaseModel):
    status: str
    timestamp: float
    version: str

class LivenessResponse(BaseModel):
    status: str
    uptime: float

class ReadinessResponse(BaseModel):
    status: str
    checks: Dict[str, bool]
    timestamp: float

_start_time = time.time()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.
    Returns service status and basic information.
    """
    return HealthResponse(
        status="healthy",
        timestamp=time.time(),
        version=settings.APP_VERSION
    )

@router.get("/liveness", response_model=LivenessResponse)
async def liveness_probe():
    """
    Kubernetes liveness probe.
    Determines if the application should be restarted.
    Returns basic status and uptime.
    """
    return LivenessResponse(
        status="alive",
        uptime=time.time() - _start_time
    )

@router.get("/readiness", response_model=ReadinessResponse)
async def readiness_probe(response: Response):
    """
    Kubernetes readiness probe.
    Determines if the application can accept traffic.
    Checks database, cache, and external service dependencies.
    """
    checks = {
        "database": await check_database(),
        "cache": await check_cache(),
        "llm_providers": await check_llm_providers()
    }
    
    all_healthy = all(checks.values())
    status = "ready" if all_healthy else "not_ready"
    
    if not all_healthy:
        response.status_code = 503
    
    return ReadinessResponse(
        status=status,
        checks=checks,
        timestamp=time.time()
    )

async def check_database() -> bool:
    """Check if database connection is healthy."""
    try:
        from app.database_connection_manager import engine
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False

async def check_cache() -> bool:
    """Check if Redis cache is healthy."""
    try:
        import redis.asyncio as redis
        from app.application_configuration import settings
        client = redis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.close()
        return True
    except Exception:
        return False

async def check_llm_providers() -> bool:
    """Check if at least one LLM provider is configured."""
    has_openai = bool(settings.OPENAI_API_KEY)
    has_anthropic = bool(settings.ANTHROPIC_API_KEY)
    return has_openai or has_anthropic

@router.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.
    Returns metrics in Prometheus text format.
    """
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@router.get("/info")
async def service_info() -> Dict[str, Any]:
    """
    Service information endpoint.
    Returns detailed service information including configuration.
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": "production" if settings.is_production else "development",
        "debug": settings.DEBUG,
        "max_concurrent_tasks": settings.MAX_CONCURRENT_TASKS,
        "task_timeout": settings.TASK_TIMEOUT,
        "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
        "rate_limit_per_minute": settings.RATE_LIMIT_PER_MINUTE,
        "uptime_seconds": time.time() - _start_time,
        "system": {
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "memory_available_gb": psutil.virtual_memory().available / (1024**3)
        }
    }
