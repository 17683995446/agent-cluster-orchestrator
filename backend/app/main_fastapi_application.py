from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
from app.application_configuration import settings
from app.core.structured_logging_config import logger, setup_logging
from app.core.enhanced_exception_handler import (
    AgentClusterException,
    register_exception_handlers
)
from app.database_connection_manager import init_db, close_db
from app.api.v1 import (
    agent_management_endpoints,
    task_execution_endpoints,
    cluster_orchestration_endpoints,
    authentication_endpoints,
    websocket_endpoints
)
from app.api import health_check_endpoints
from app.api import api_documentation
from app.observability.opentelemetry_tracing import setup_telemetry
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

setup_logging(settings.LOG_LEVEL, settings.LOG_FORMAT)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_startup", version=settings.APP_VERSION)
    
    setup_telemetry(app)
    logger.info("opentelemetry_initialized")
    
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.warning("database_init_skipped", reason=str(e))
    
    yield
    
    logger.info("application_shutdown")
    await close_db()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready Agent Cluster Orchestration System",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

register_exception_handlers(app)

app.include_router(health_check_endpoints.router)
app.include_router(agent_management_endpoints.router, prefix="/api/v1")
app.include_router(task_execution_endpoints.router, prefix="/api/v1")
app.include_router(cluster_orchestration_endpoints.router, prefix="/api/v1")
app.include_router(authentication_endpoints.router, prefix="/api/v1")
app.include_router(websocket_endpoints.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main_fastapi_application:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
