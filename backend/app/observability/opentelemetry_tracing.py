"""
OpenTelemetry configuration and tracing setup for Agent Cluster Orchestrator.
Provides distributed tracing across all services.
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.trace import Status, StatusCode
from contextlib import contextmanager
from typing import Optional, Dict, Any
import structlog

from app.application_configuration import settings

logger = structlog.get_logger()

_tracer: Optional[trace.Tracer] = None


def setup_telemetry(app=None):
    """
    Initialize OpenTelemetry with tracing and metrics.
    Call this during application startup.
    """
    global _tracer
    
    resource = Resource.create({
        SERVICE_NAME: settings.APP_NAME,
        SERVICE_VERSION: settings.APP_VERSION,
        "deployment.environment": "production" if settings.is_production else "development",
    })
    
    provider = TracerProvider(resource=resource)
    
    if settings.DEBUG:
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
        logger.info("opentelemetry_console_exporter_enabled")
    
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(__name__, settings.APP_VERSION)
    
    if app:
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
        logger.info("opentelemetry_instrumentation_enabled")
    
    return _tracer


def get_tracer() -> trace.Tracer:
    """Get the configured tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(__name__, settings.APP_VERSION)
    return _tracer


@contextmanager
def traced_operation(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True
):
    """
    Context manager for tracing operations.
    
    Usage:
        with traced_operation("process_task", {"task_id": "123"}):
            process_task()
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value) if value is not None else "")
        
        try:
            yield span
        except Exception as e:
            if record_exception:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
            raise


async def traced_async_operation(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True
):
    """
    Async context manager for tracing async operations.
    
    Usage:
        async with traced_async_operation("llm_call", {"provider": "openai"}):
            await llm_call()
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value) if value is not None else "")
        
        try:
            yield span
        except Exception as e:
            if record_exception:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
            raise


def add_span_attribute(key: str, value: Any) -> None:
    """Add attribute to current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_attribute(key, str(value) if value is not None else "")


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
    """Add event to current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes or {})


def record_exception(exception: Exception, attributes: Optional[Dict[str, Any]] = None) -> None:
    """Record exception in current span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR, str(exception)))
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value) if value is not None else "")


class TracingMiddleware:
    """
    Middleware for adding tracing to operations.
    Can be used to wrap service calls.
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.tracer = get_tracer()
    
    def __call__(self, operation_name: str):
        """Decorator for tracing functions."""
        def decorator(func):
            async def async_wrapper(*args, **kwargs):
                with traced_operation(
                    f"{self.service_name}.{operation_name}",
                    {"service": self.service_name, "operation": operation_name}
                ):
                    return await func(*args, **kwargs)
            
            def sync_wrapper(*args, **kwargs):
                with traced_operation(
                    f"{self.service_name}.{operation_name}",
                    {"service": self.service_name, "operation": operation_name}
                ):
                    return func(*args, **kwargs)
            
            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        
        return decorator


tracing_middleware = TracingMiddleware(settings.APP_NAME)
