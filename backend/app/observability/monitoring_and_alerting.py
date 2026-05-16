"""
Advanced Monitoring and Alerting System
Production-ready observability with intelligent alerting.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger()


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = auto()
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()
    INFO = auto()


class AlertStatus(Enum):
    """Alert status."""
    FIRING = auto()
    RESOLVED = auto()
    ACKNOWLEDGED = auto()
    SUPPRESSED = auto()


@dataclass
class Alert:
    """Alert representation."""
    name: str
    severity: AlertSeverity
    message: str
    status: AlertStatus = AlertStatus.FIRING
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    fired_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    count: int = 1


@dataclass
class MetricValue:
    """Metric value with timestamp."""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = field(default_factory=dict)


class AlertRule:
    """Rule for triggering alerts."""

    def __init__(
        self,
        name: str,
        condition: Callable[["AlertManager"], bool],
        severity: AlertSeverity,
        message: str,
        labels: Optional[Dict[str, str]] = None,
        annotations: Optional[Dict[str, str]] = None,
        cooldown_seconds: int = 60
    ):
        self.name = name
        self.condition = condition
        self.severity = severity
        self.message = message
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.cooldown_seconds = cooldown_seconds
        self._last_fired: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def should_fire(self) -> bool:
        """Check if alert should fire based on cooldown."""
        async with self._lock:
            if self._last_fired:
                elapsed = (datetime.utcnow() - self._last_fired).total_seconds()
                if elapsed < self.cooldown_seconds:
                    return False
            return self.condition(alert_manager)

    def mark_fired(self):
        """Mark alert as fired."""
        self._last_fired = datetime.utcnow()

    def reset(self):
        """Reset last fired time."""
        self._last_fired = None


class AlertManager:
    """
    Centralized alert management system.
    
    Features:
    - Intelligent alert rules
    - Alert grouping and deduplication
    - Alert suppression
    - Alert history
    - Integration hooks
    """

    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        self._notification_hooks: List[Callable[[Alert], None]] = []
        self._suppression_filters: List[Callable[[Alert], bool]] = []
        self._lock = asyncio.Lock()
        self._max_history_size = 1000

    def register_rule(self, rule: AlertRule):
        """Register an alert rule."""
        self._rules[rule.name] = rule
        logger.info("alert_rule_registered", rule=rule.name, severity=rule.severity.name)

    def register_notification_hook(self, hook: Callable[[Alert], None]):
        """Register a notification hook."""
        self._notification_hooks.append(hook)

    def add_suppression_filter(self, filter_func: Callable[[Alert], bool]):
        """Add an alert suppression filter."""
        self._suppression_filters.append(filter_func)

    async def evaluate_rules(self) -> List[Alert]:
        """Evaluate all rules and generate alerts."""
        new_alerts = []

        for rule in self._rules.values():
            try:
                if await rule.should_fire():
                    if rule.condition(self):
                        alert = Alert(
                            name=rule.name,
                            severity=rule.severity,
                            message=rule.message,
                            labels=rule.labels.copy(),
                            annotations=rule.annotations.copy()
                        )

                        if await self._should_process(alert):
                            existing = self._active_alerts.get(rule.name)
                            if existing:
                                existing.count += 1
                                new_alerts.append(existing)
                            else:
                                self._active_alerts[rule.name] = alert
                                new_alerts.append(alert)
                                rule.mark_fired()

            except Exception as e:
                logger.error("alert_rule_evaluation_failed", rule=rule.name, error=str(e))

        for alert in new_alerts:
            await self._notify(alert)

        return new_alerts

    async def _should_process(self, alert: Alert) -> bool:
        """Check if alert should be processed."""
        for filter_func in self._suppression_filters:
            if filter_func(alert):
                return False
        return True

    async def _notify(self, alert: Alert):
        """Send notification for alert."""
        for hook in self._notification_hooks:
            try:
                hook(alert)
            except Exception as e:
                logger.error("alert_notification_failed", hook=str(hook), error=str(e))

    async def acknowledge_alert(self, alert_name: str) -> bool:
        """Acknowledge an active alert."""
        async with self._lock:
            if alert_name in self._active_alerts:
                alert = self._active_alerts[alert_name]
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = datetime.utcnow()
                return True
            return False

    async def resolve_alert(self, alert_name: str) -> bool:
        """Resolve an active alert."""
        async with self._lock:
            if alert_name in self._active_alerts:
                alert = self._active_alerts.pop(alert_name)
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.utcnow()
                self._add_to_history(alert)

                rule = self._rules.get(alert_name)
                if rule:
                    rule.reset()

                return True
            return False

    async def suppress_alert(self, alert_name: str, duration_seconds: int) -> bool:
        """Temporarily suppress an alert."""
        async with self._lock:
            if alert_name in self._active_alerts:
                alert = self._active_alerts[alert_name]
                alert.status = AlertStatus.SUPPRESSED
                asyncio.create_task(self._unsuppress_after(alert_name, duration_seconds))
                return True
            return False

    async def _unsuppress_after(self, alert_name: str, duration_seconds: int):
        """Unsuppress alert after duration."""
        await asyncio.sleep(duration_seconds)
        async with self._lock:
            if alert_name in self._active_alerts:
                alert = self._active_alerts[alert_name]
                if alert.status == AlertStatus.SUPPRESSED:
                    alert.status = AlertStatus.FIRING

    def _add_to_history(self, alert: Alert):
        """Add alert to history."""
        self._alert_history.append(alert)
        if len(self._alert_history) > self._max_history_size:
            self._alert_history = self._alert_history[-self._max_history_size:]

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self._active_alerts.values())

    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history."""
        return self._alert_history[-limit:]

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of alert states."""
        summary = {
            "total_active": len(self._active_alerts),
            "by_severity": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0
            },
            "by_status": {
                "firing": 0,
                "acknowledged": 0,
                "suppressed": 0
            },
            "total_history": len(self._alert_history)
        }

        for alert in self._active_alerts.values():
            severity_key = alert.severity.name.lower()
            summary["by_severity"][severity_key] += 1

            status_key = alert.status.name.lower()
            if status_key in summary["by_status"]:
                summary["by_status"][status_key] += 1

        return summary


class MetricsCollector:
    """
    Metrics collection and aggregation.
    
    Features:
    - Counter metrics
    - Gauge metrics
    - Histogram metrics
    - Summary metrics
    - Custom aggregations
    """

    def __init__(self):
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._time_series: Dict[str, List[MetricValue]] = {}
        self._lock = asyncio.Lock()
        self._max_series_size = 10000

    async def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        async with self._lock:
            key = self._make_key(name, labels)
            self._counters[key] = self._counters.get(key, 0) + value

    async def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric."""
        async with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value
            await self._record_time_series(name, value, labels)

    async def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram observation."""
        async with self._lock:
            key = self._make_key(name, labels)
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)
            if len(self._histograms[key]) > 10000:
                self._histograms[key] = self._histograms[key][-10000:]

    async def _record_time_series(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record time series data point."""
        key = self._make_key(name, labels)
        if key not in self._time_series:
            self._time_series[key] = []
        self._time_series[key].append(MetricValue(name=name, value=value, labels=labels or {}))
        if len(self._time_series[key]) > self._max_series_size:
            self._time_series[key] = self._time_series[key][-self._max_series_size:]

    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create metric key from name and labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get counter value."""
        key = self._make_key(name, labels)
        return self._counters.get(key, 0)

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get gauge value."""
        key = self._make_key(name, labels)
        return self._gauges.get(key)

    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(name, labels)
        values = self._histograms.get(key, [])

        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}

        sorted_values = sorted(values)
        n = len(sorted_values)

        return {
            "count": n,
            "sum": sum(sorted_values),
            "avg": sum(sorted_values) / n,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "p50": sorted_values[int(n * 0.5)],
            "p90": sorted_values[int(n * 0.9)],
            "p95": sorted_values[int(n * 0.95)],
            "p99": sorted_values[int(n * 0.99)] if n > 100 else sorted_values[-1]
        }

    def get_time_series(self, name: str, labels: Optional[Dict[str, str]] = None, limit: int = 100) -> List[MetricValue]:
        """Get time series data."""
        key = self._make_key(name, labels)
        return self._time_series.get(key, [])[-limit:]

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics snapshot."""
        return {
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "histograms": {
                k: self.get_histogram_stats(k) for k in self._histograms.keys()
            }
        }


class MonitoringDashboard:
    """
    Real-time monitoring dashboard data provider.
    
    Provides aggregated metrics and health status.
    """

    def __init__(
        self,
        alert_manager: AlertManager,
        metrics_collector: MetricsCollector
    ):
        self.alert_manager = alert_manager
        self.metrics_collector = metrics_collector
        self._health_checks: Dict[str, Callable[[], bool]] = {}

    def register_health_check(self, name: str, check: Callable[[], bool]):
        """Register a health check function."""
        self._health_checks[name] = check

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        health_status = {"healthy": True, "checks": {}, "overall_score": 100}

        for name, check in self._health_checks.items():
            try:
                is_healthy = check()
                health_status["checks"][name] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "checked_at": datetime.utcnow().isoformat()
                }
                if not is_healthy:
                    health_status["healthy"] = False
                    health_status["overall_score"] -= 10
            except Exception as e:
                health_status["checks"][name] = {
                    "status": "error",
                    "error": str(e),
                    "checked_at": datetime.utcnow().isoformat()
                }
                health_status["healthy"] = False
                health_status["overall_score"] -= 20

        return health_status

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get dashboard data for visualization."""
        alert_summary = self.alert_manager.get_alert_summary()
        metrics = self.metrics_collector.get_all_metrics()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "health": self.get_system_health(),
            "alerts": {
                "summary": alert_summary,
                "active": [
                    {
                        "name": a.name,
                        "severity": a.severity.name,
                        "status": a.status.name,
                        "message": a.message,
                        "count": a.count,
                        "fired_at": a.fired_at.isoformat()
                    }
                    for a in self.alert_manager.get_active_alerts()
                ]
            },
            "metrics": metrics
        }


class SLOTracker:
    """
    Service Level Objective tracker.
    
    Features:
    - SLO definition and tracking
    - Availability calculation
    - Latency SLO tracking
    - Error budget monitoring
    """

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self._slos: Dict[str, Dict[str, Any]] = {}

    def define_slo(
        self,
        name: str,
        target: float,
        window: str = "30d",
        metric_type: str = "availability"
    ):
        """Define an SLO."""
        self._slos[name] = {
            "target": target,
            "window": window,
            "metric_type": metric_type,
            "created_at": datetime.utcnow()
        }

    async def record_success(self, slo_name: str):
        """Record a successful request."""
        await self.metrics_collector.increment_counter(f"slo_{slo_name}_success")

    async def record_failure(self, slo_name: str):
        """Record a failed request."""
        await self.metrics_collector.increment_counter(f"slo_{slo_name}_failure")

    def get_slo_status(self, slo_name: str) -> Dict[str, Any]:
        """Get current SLO status."""
        if slo_name not in self._slos:
            return {"error": f"SLO {slo_name} not found"}

        slo = self._slos[slo_name]
        success = self.metrics_collector.get_counter(f"slo_{slo_name}_success")
        failure = self.metrics_collector.get_counter(f"slo_{slo_name}_failure")
        total = success + failure

        if total == 0:
            current_value = 1.0
        else:
            current_value = success / total

        target = slo["target"]
        error_budget_remaining = max(0, (target - current_value) * 100)
        error_budget_consumed = 100 - target - error_budget_remaining

        return {
            "name": slo_name,
            "target": target,
            "current": current_value,
            "error_budget_remaining": error_budget_remaining,
            "total_requests": total,
            "window": slo["window"],
            "status": "healthy" if current_value >= target else "breaching"
        }


alert_manager = AlertManager()
metrics_collector = MetricsCollector()
monitoring_dashboard = MonitoringDashboard(alert_manager, metrics_collector)
slo_tracker = SLOTracker(metrics_collector)


def setup_default_alert_rules():
    """Setup default monitoring alert rules."""

    def high_error_rate() -> bool:
        error_rate = metrics_collector.get_gauge("system_error_rate") or 0
        return error_rate > 0.05

    def high_latency() -> bool:
        p95 = metrics_collector.get_histogram_stats("request_latency").get("p95", 0)
        return p95 > 1.0

    def low_availability() -> bool:
        uptime = metrics_collector.get_gauge("system_uptime") or 1.0
        return uptime < 0.99

    alert_manager.register_rule(AlertRule(
        name="high_error_rate",
        condition=lambda am: high_error_rate(),
        severity=AlertSeverity.HIGH,
        message="系统错误率超过5%",
        labels={"service": "agent-cluster"},
        cooldown_seconds=60
    ))

    alert_manager.register_rule(AlertRule(
        name="high_latency",
        condition=lambda am: high_latency(),
        severity=AlertSeverity.MEDIUM,
        message="请求延迟P95超过1秒",
        labels={"service": "agent-cluster"},
        cooldown_seconds=120
    ))

    alert_manager.register_rule(AlertRule(
        name="low_availability",
        condition=lambda am: low_availability(),
        severity=AlertSeverity.CRITICAL,
        message="系统可用性低于99%",
        labels={"service": "agent-cluster"},
        cooldown_seconds=300
    ))
