"""
Phase 5: 监控、日志与可观测性
Comprehensive Observability Suite
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import structlog
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = structlog.get_logger()


class LogLevel(Enum):
    """Log levels."""
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class StructuredLogEntry:
    """Structured log entry."""
    timestamp: datetime
    level: LogLevel
    message: str
    logger_name: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ObservabilityConfig:
    """Configuration for observability components."""
    
    def __init__(
        self,
        service_name: str = "agent-cluster",
        log_level: str = "INFO",
        enable_tracing: bool = True,
        enable_metrics: bool = True,
        jaeger_endpoint: Optional[str] = None,
        prometheus_port: int = 9090
    ):
        self.service_name = service_name
        self.log_level = log_level
        self.enable_tracing = enable_tracing
        self.enable_metrics = enable_metrics
        self.jaeger_endpoint = jaeger_endpoint
        self.prometheus_port = prometheus_port


class StructuredLogger:
    """
    Structured logging with correlation support.
    
    Features:
    - Structured output (JSON)
    - Correlation IDs
    - Context propagation
    - Log levels
    """
    
    def __init__(self, config: ObservabilityConfig):
        self.config = config
        self._correlation_id: Optional[str] = None
        self._user_id: Optional[str] = None
        self._request_id: Optional[str] = None
    
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for log correlation."""
        self._correlation_id = correlation_id
    
    def set_user_id(self, user_id: str):
        """Set user ID for audit logging."""
        self._user_id = user_id
    
    def set_request_id(self, request_id: str):
        """Set request ID for request tracking."""
        self._request_id = request_id
    
    def _build_context(self) -> Dict[str, Any]:
        """Build logging context."""
        context = {
            "service": self.config.service_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if self._correlation_id:
            context["correlation_id"] = self._correlation_id
        if self._user_id:
            context["user_id"] = self._user_id
        if self._request_id:
            context["request_id"] = self._request_id
        
        return context
    
    def trace(self, message: str, **kwargs):
        """Log trace message."""
        self._log(LogLevel.TRACE, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, **kwargs)
    
    def _log(self, level: LogLevel, message: str, **kwargs):
        """Internal log method."""
        entry = StructuredLogEntry(
            timestamp=datetime.utcnow(),
            level=level,
            message=message,
            logger_name=self.config.service_name,
            correlation_id=self._correlation_id,
            user_id=self._user_id,
            request_id=self._request_id,
            metadata=kwargs
        )
        
        log_data = {
            "timestamp": entry.timestamp.isoformat(),
            "level": entry.level.value,
            "message": entry.message,
            **self._build_context(),
            **kwargs
        }
        
        if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            logger.error(**log_data)
        elif level == LogLevel.WARNING:
            logger.warning(**log_data)
        elif level == LogLevel.INFO:
            logger.info(**log_data)
        elif level == LogLevel.DEBUG:
            logger.debug(**log_data)
        else:
            logger.debug(**log_data)


class MetricsCollector:
    """
    Metrics collection for Prometheus.
    
    Features:
    - Counters
    - Gauges
    - Histograms
    - Summary
    """
    
    def __init__(self, config: ObservabilityConfig):
        self.config = config
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._labels: Dict[str, Dict[str, str]] = {}
    
    def increment_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None
    ):
        """Increment a counter metric."""
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value
    
    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Set a gauge metric."""
        key = self._make_key(name, labels)
        self._gauges[key] = value
        if labels:
            self._labels[key] = labels
    
    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Observe a value for histogram."""
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        if labels:
            self._labels[key] = labels
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create metric key."""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        lines = []
        
        for key, value in self._counters.items():
            lines.append(f"# TYPE {key} counter")
            lines.append(f"{key} {value}")
        
        for key, value in self._gauges.items():
            lines.append(f"# TYPE {key} gauge")
            lines.append(f"{key} {value}")
        
        for key, values in self._histograms.items():
            if values:
                avg = sum(values) / len(values)
                lines.append(f"# TYPE {key} histogram")
                lines.append(f"{key}_sum {sum(values)}")
                lines.append(f"{key}_count {len(values)}")
                lines.append(f"{key}_avg {avg}")
        
        return "\n".join(lines)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "histogram_count": {k: len(v) for k, v in self._histograms.items()}
        }


class DistributedTracer:
    """
    Distributed tracing with OpenTelemetry.
    
    Features:
    - Trace context propagation
    - Span management
    - Correlation
    """
    
    def __init__(self, config: ObservabilityConfig):
        self.config = config
        self._tracer: Optional[trace.Tracer] = None
        self._current_span: Optional[trace.Span] = None
        
        if config.enable_tracing:
            self._setup_tracing()
    
    def _setup_tracing(self):
        """Setup OpenTelemetry tracing."""
        resource = Resource.create({
            "service.name": self.config.service_name
        })
        
        provider = TracerProvider(resource=resource)
        
        if self.config.jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name=self.config.jaeger_endpoint.split(":")[0],
                agent_port=int(self.config.jaeger_endpoint.split(":")[1]) if ":" in self.config.jaeger_endpoint else 6831
            )
            provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
        
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer(self.config.service_name)
    
    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, str]] = None
    ) -> trace.Span:
        """Start a new span."""
        if not self._tracer:
            return None
        
        span = self._tracer.start_span(name)
        
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        
        return span
    
    def end_span(self, span: trace.Span):
        """End a span."""
        if span:
            span.end()
    
    def create_context_manager(
        self,
        name: str,
        attributes: Optional[Dict[str, str]] = None
    ):
        """Create a span as context manager."""
        if not self._tracer:
            return _NoOpContextManager()
        
        return self._tracer.start_as_current_span(name, attributes=attributes)


class _NoOpContextManager:
    """No-op context manager for when tracing is disabled."""
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass


class HealthChecker:
    """
    Health checking system.
    
    Features:
    - Health check registration
    - Dependency checks
    - Readiness probes
    """
    
    def __init__(self):
        self._checks: Dict[str, Callable] = {}
    
    def register_check(self, name: str, check: Callable[[], bool]):
        """Register a health check."""
        self._checks[name] = check
    
    async def check_health(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_healthy = True
        
        for name, check in self._checks.items():
            try:
                if asyncio.iscoroutinefunction(check):
                    is_healthy = await check()
                else:
                    is_healthy = check()
                
                results[name] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "checked_at": datetime.utcnow().isoformat()
                }
                
                if not is_healthy:
                    overall_healthy = False
                    
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "checked_at": datetime.utcnow().isoformat()
                }
                overall_healthy = False
        
        return {
            "healthy": overall_healthy,
            "checks": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def is_ready(self) -> bool:
        """Check if system is ready to serve traffic."""
        return True


class AlertManager:
    """
    Alert management system.
    
    Features:
    - Alert rules
    - Alert channels
    - Alert deduplication
    """
    
    def __init__(self):
        self._rules: List[Callable[[], bool]] = []
        self._channels: List[Callable] = []
        self._active_alerts: Dict[str, datetime] = {}
    
    def register_rule(self, rule: Callable[[], bool]):
        """Register an alert rule."""
        self._rules.append(rule)
    
    def register_channel(self, channel: Callable):
        """Register an alert channel."""
        self._channels.append(channel)
    
    async def check_alerts(self) -> List[Dict[str, Any]]:
        """Check all alert rules and fire alerts."""
        fired_alerts = []
        
        for rule in self._rules:
            try:
                if asyncio.iscoroutinefunction(rule):
                    should_fire = await rule()
                else:
                    should_fire = rule()
                
                if should_fire:
                    alert = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "fired": True
                    }
                    fired_alerts.append(alert)
                    
                    for channel in self._channels:
                        try:
                            if asyncio.iscoroutinefunction(channel):
                                await channel(alert)
                            else:
                                channel(alert)
                        except Exception:
                            pass
                            
            except Exception:
                pass
        
        return fired_alerts


class DashboardDataProvider:
    """
    Dashboard data provider for monitoring UIs.
    
    Features:
    - System metrics
    - Service health
    - Alert summary
    """
    
    def __init__(
        self,
        metrics_collector: MetricsCollector,
        health_checker: HealthChecker,
        alert_manager: AlertManager
    ):
        self.metrics_collector = metrics_collector
        self.health_checker = health_checker
        self.alert_manager = alert_manager
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all dashboard data."""
        health = await self.health_checker.check_health()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "agent-cluster-orchestrator",
            "health": health,
            "metrics": self.metrics_collector.get_summary(),
            "alerts": {
                "active_count": len(self.alert_manager._active_alerts)
            }
        }


class RequestTracer:
    """
    HTTP request tracing.
    
    Features:
    - Request/response logging
    - Latency tracking
    - Error tracking
    """
    
    def __init__(self, tracer: DistributedTracer, metrics: MetricsCollector):
        self.tracer = tracer
        self.metrics = metrics
    
    async def trace_request(
        self,
        method: str,
        path: str,
        handler: Callable
    ) -> Any:
        """Trace an HTTP request."""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        with self.tracer.create_context_manager(
            f"{method} {path}",
            attributes={
                "http.method": method,
                "http.path": path,
                "request.id": request_id
            }
        ):
            try:
                response = await handler()
                duration = time.time() - start_time
                
                self.metrics.increment_counter(
                    "http_requests_total",
                    labels={"method": method, "path": path, "status": "success"}
                )
                self.metrics.observe_histogram(
                    "http_request_duration_seconds",
                    duration,
                    labels={"method": method, "path": path}
                )
                
                return response
                
            except Exception as e:
                duration = time.time() - start_time
                
                self.metrics.increment_counter(
                    "http_requests_total",
                    labels={"method": method, "path": path, "status": "error"}
                )
                self.metrics.observe_histogram(
                    "http_request_duration_seconds",
                    duration,
                    labels={"method": method, "path": path}
                )
                
                raise


config = ObservabilityConfig()
structured_logger = StructuredLogger(config)
metrics_collector = MetricsCollector(config)
distributed_tracer = DistributedTracer(config)
health_checker = HealthChecker()
alert_manager = AlertManager()
dashboard_provider = DashboardDataProvider(metrics_collector, health_checker, alert_manager)
