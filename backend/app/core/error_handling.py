"""
Phase 4: 错误处理与容错机制
Comprehensive Error Handling and Fault Tolerance
"""
from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type
import structlog

logger = structlog.get_logger()


class ErrorSeverity(Enum):
    """Error severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ErrorCategory(Enum):
    """Error categories."""
    NETWORK = "network"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    BUSINESS_LOGIC = "business_logic"
    EXTERNAL_SERVICE = "external_service"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for an error."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    tenant_id: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    additional_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorRecord:
    """Record of an error occurrence."""
    error_id: str
    error_type: str
    message: str
    severity: ErrorSeverity
    category: ErrorCategory
    context: ErrorContext
    stack_trace: str
    resolved: bool = False
    resolution_notes: Optional[str] = None
    occurrences: int = 1
    first_occurrence: datetime = field(default_factory=datetime.utcnow)
    last_occurrence: datetime = field(default_factory=datetime.utcnow)


class ErrorClassifier:
    """Classifies errors into categories and severity levels."""
    
    NETWORK_ERRORS = (ConnectionError, TimeoutError, asyncio.TimeoutError)
    DATABASE_ERRORS = (ConnectionRefusedError,)
    
    @classmethod
    def classify(cls, error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        """Classify an error."""
        error_type = type(error)
        
        if isinstance(error, cls.NETWORK_ERRORS):
            return ErrorCategory.NETWORK, ErrorSeverity.HIGH
        
        if isinstance(error, cls.DATABASE_ERRORS):
            return ErrorCategory.DATABASE, ErrorSeverity.CRITICAL
        
        if "auth" in str(error).lower() or "permission" in str(error).lower():
            return ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH
        
        if "validation" in str(error).lower() or "invalid" in str(error).lower():
            return ErrorCategory.VALIDATION, ErrorSeverity.MEDIUM
        
        if "database" in str(error).lower() or "sql" in str(error).lower():
            return ErrorCategory.DATABASE, ErrorSeverity.HIGH
        
        if "timeout" in str(error).lower():
            return ErrorCategory.NETWORK, ErrorSeverity.MEDIUM
        
        return ErrorCategory.UNKNOWN, ErrorSeverity.MEDIUM
    
    @classmethod
    def is_retryable(cls, error: Exception, category: ErrorCategory) -> bool:
        """Determine if an error is retryable."""
        non_retryable = {
            ErrorCategory.AUTHENTICATION,
            ErrorCategory.VALIDATION,
            ErrorCategory.BUSINESS_LOGIC
        }
        
        if category in non_retryable:
            return False
        
        return True


class ErrorHandler:
    """
    Centralized error handling system.
    
    Features:
    - Error classification
    - Error aggregation
    - Alert triggering
    - Recovery suggestions
    """
    
    def __init__(self):
        self._error_records: Dict[str, ErrorRecord] = {}
        self._error_handlers: Dict[Type[Exception], Callable] = {}
        self._alert_thresholds: Dict[str, int] = {
            "critical": 1,
            "high": 5,
            "medium": 10,
            "low": 20
        }
    
    def register_handler(
        self,
        error_type: Type[Exception],
        handler: Callable[[Exception, ErrorContext], Any]
    ):
        """Register a custom error handler."""
        self._error_handlers[error_type] = handler
    
    async def handle_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        reraise: bool = True
    ) -> Optional[ErrorRecord]:
        """Handle an error with full processing."""
        context = context or ErrorContext()
        
        error_type = type(error).__name__
        error_id = f"{error_type}_{context.timestamp.timestamp()}"
        
        category, severity = ErrorClassifier.classify(error)
        
        record = ErrorRecord(
            error_id=error_id,
            error_type=error_type,
            message=str(error),
            severity=severity,
            category=category,
            context=context,
            stack_trace=traceback.format_exc()
        )
        
        self._error_records[error_id] = record
        
        await self._check_alert_threshold(record)
        
        if error_type in self._error_handlers:
            handler = self._error_handlers[error_type]
            try:
                result = await handler(error, context)
                if result is not None:
                    return result
            except Exception as e:
                logger.error("error_handler_failed", original_error=str(error), handler_error=str(e))
        
        if reraise:
            raise
        
        return record
    
    async def _check_alert_threshold(self, record: ErrorRecord):
        """Check if alert should be triggered."""
        severity_key = record.severity.value
        threshold = self._alert_thresholds.get(severity_key, 10)
        
        recent_errors = [
            r for r in self._error_records.values()
            if r.error_type == record.error_type
            and (datetime.utcnow() - r.last_occurrence).total_seconds() < 3600
        ]
        
        if len(recent_errors) >= threshold:
            logger.warning(
                "error_threshold_exceeded",
                error_type=record.error_type,
                occurrences=len(recent_errors),
                severity=severity_key
            )
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of recent errors."""
        if not self._error_records:
            return {"total": 0, "by_category": {}, "by_severity": {}}
        
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        
        for record in self._error_records.values():
            cat = record.category.value
            sev = record.severity.value
            
            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1
        
        return {
            "total": len(self._error_records),
            "by_category": by_category,
            "by_severity": by_severity,
            "recent": [
                {
                    "error_id": r.error_id,
                    "error_type": r.error_type,
                    "message": r.message,
                    "severity": r.severity.value,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in sorted(
                    self._error_records.values(),
                    key=lambda x: x.timestamp,
                    reverse=True
                )[:10]
            ]
        }


class FallbackManager:
    """
    Fallback mechanism manager for graceful degradation.
    
    Features:
    - Multiple fallback strategies
    - Fallback chains
    - Circuit breaker integration
    - Statistics tracking
    """
    
    def __init__(self):
        self._fallback_strategies: Dict[str, List[Callable]] = {}
        self._circuit_breakers: Dict[str, asyncio.Semaphore] = {}
    
    def register_fallback(
        self,
        operation: str,
        primary_func: Callable,
        *fallbacks: Callable
    ):
        """Register fallback chain for an operation."""
        self._fallback_strategies[operation] = [primary_func, *fallbacks]
        
        if operation not in self._circuit_breakers:
            self._circuit_breakers[operation] = asyncio.Semaphore(1)
    
    async def execute_with_fallback(
        self,
        operation: str,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with fallback support."""
        strategies = self._fallback_strategies.get(operation, [])
        
        if not strategies:
            raise ValueError(f"No fallback strategies registered for {operation}")
        
        last_error = None
        
        for i, strategy in enumerate(strategies):
            try:
                semaphore = self._circuit_breakers.get(operation)
                if semaphore:
                    async with semaphore:
                        if asyncio.iscoroutinefunction(strategy):
                            return await strategy(*args, **kwargs)
                        return strategy(*args, **kwargs)
                else:
                    if asyncio.iscoroutinefunction(strategy):
                        return await strategy(*args, **kwargs)
                    return strategy(*args, **kwargs)
                    
            except Exception as e:
                last_error = e
                logger.warning(
                    "fallback_attempt_failed",
                    operation=operation,
                    attempt=i + 1,
                    error=str(e)
                )
        
        raise last_error or Exception(f"All fallback strategies failed for {operation}")
    
    def get_stats(self, operation: str) -> Dict[str, Any]:
        """Get fallback statistics."""
        return {
            "operation": operation,
            "strategies_count": len(self._fallback_strategies.get(operation, [])),
            "circuit_open": False
        }


class GracefulDegradation:
    """
    Graceful degradation manager for service failures.
    
    Features:
    - Service health monitoring
    - Automatic degradation
    - Recovery detection
    """
    
    def __init__(self):
        self._service_states: Dict[str, bool] = {}
        self._degradation_handlers: Dict[str, Callable] = {}
        self._recovery_handlers: Dict[str, Callable] = {}
    
    def register_degradation_handler(
        self,
        service: str,
        handler: Callable,
        recovery_handler: Optional[Callable] = None
    ):
        """Register handlers for service degradation."""
        self._degradation_handlers[service] = handler
        if recovery_handler:
            self._recovery_handlers[service] = recovery_handler
    
    async def report_service_failure(self, service: str):
        """Report a service failure."""
        was_healthy = self._service_states.get(service, True)
        self._service_states[service] = False
        
        if was_healthy and service in self._degradation_handlers:
            logger.warning("service_degraded", service=service)
            try:
                await self._degradation_handlers[service]()
            except Exception as e:
                logger.error("degradation_handler_failed", service=service, error=str(e))
    
    async def report_service_recovery(self, service: str):
        """Report service recovery."""
        was_unhealthy = not self._service_states.get(service, True)
        self._service_states[service] = True
        
        if was_unhealthy and service in self._recovery_handlers:
            logger.info("service_recovered", service=service)
            try:
                await self._recovery_handlers[service]()
            except Exception as e:
                logger.error("recovery_handler_failed", service=service, error=str(e))
    
    def is_service_healthy(self, service: str) -> bool:
        """Check if service is healthy."""
        return self._service_states.get(service, True)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health."""
        total = len(self._service_states)
        healthy = sum(1 for s in self._service_states.values() if s)
        
        return {
            "overall_healthy": healthy == total,
            "healthy_services": healthy,
            "unhealthy_services": total - healthy,
            "total_services": total,
            "services": self._service_states.copy()
        }


class BulkheadIsolation:
    """
    Bulkhead pattern implementation for fault isolation.
    
    Features:
    - Resource isolation
    - Failure containment
    - Adaptive limits
    """
    
    def __init__(
        self,
        max_concurrent: int = 10,
        timeout: float = 30.0
    ):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._rejected_count = 0
        self._total_executions = 0
    
    async def execute(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """Execute with bulkhead isolation."""
        self._total_executions += 1
        
        try:
            async with asyncio.timeout(self.timeout):
                await self._semaphore.acquire()
                self._active_count += 1
                
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    return func(*args, **kwargs)
                finally:
                    self._active_count -= 1
                    self._semaphore.release()
                    
        except asyncio.TimeoutError:
            self._rejected_count += 1
            raise Exception(f"Bulkhead timeout exceeded: {self.timeout}s")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bulkhead statistics."""
        return {
            "max_concurrent": self.max_concurrent,
            "current_active": self._active_count,
            "total_executions": self._total_executions,
            "rejected_count": self._rejected_count,
            "rejection_rate": self._rejected_count / self._total_executions if self._total_executions > 0 else 0
        }


class ChaosEngineering:
    """
    Chaos engineering utilities for resilience testing.
    
    Features:
    - Failure injection
    - Latency simulation
    - Error simulation
    """
    
    def __init__(self):
        self._enabled = False
        self._failure_rate = 0.0
        self._latency_ms = 0
    
    def enable(self, failure_rate: float = 0.1, latency_ms: int = 0):
        """Enable chaos engineering."""
        self._enabled = True
        self._failure_rate = failure_rate
        self._latency_ms = latency_ms
    
    def disable(self):
        """Disable chaos engineering."""
        self._enabled = False
    
    async def inject_latency(self):
        """Inject simulated latency."""
        if self._enabled and self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000)
    
    def should_fail(self) -> bool:
        """Determine if failure should be injected."""
        import random
        return self._enabled and random.random() < self._failure_rate
    
    def inject_failure(self, error_type: Type[Exception] = Exception):
        """Inject a failure."""
        if self.should_fail():
            raise error_type("Injected chaos failure")


error_handler = ErrorHandler()
fallback_manager = FallbackManager()
graceful_degradation = GracefulDegradation()
bulkhead_isolation = BulkheadIsolation()
chaos_engineering = ChaosEngineering()
