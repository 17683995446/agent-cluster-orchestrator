"""
Agent Cluster Orchestrator - Timeout Protection Module

Provides timeout control and monitoring for asynchronous task execution.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TimeoutConfig:
    """Configuration parameters for timeout protection behavior."""
    default_timeout: float = 5.0
    max_timeout: float = 30.0
    enable_timeout_protection: bool = True


class TimeoutError(Exception):
    """Exception raised when task execution exceeds specified timeout."""
    pass


async def execute_with_timeout(
    coro,
    timeout: float,
    task_name: Optional[str] = None
) -> Any:
    """
    Execute coroutine with timeout protection mechanism.
    
    Args:
        coro: Coroutine or callable to execute
        timeout: Timeout duration in seconds
        task_name: Name of task for logging purposes
        
    Returns:
        Coroutine execution result
        
    Raises:
        TimeoutError: When execution exceeds specified timeout duration
    """
    task_name = task_name or "anonymous"
    
    try:
        result = await asyncio.wait_for(
            coro if asyncio.iscoroutine(coro) else coro(),
            timeout=timeout
        )
        return result
        
    except asyncio.TimeoutError:
        logger.warning(
            "task_timeout",
            task_name=task_name,
            timeout=timeout
        )
        raise TimeoutError(
            f"Task '{task_name}' exceeded timeout of {timeout}s"
        )


class TimeoutMonitor:
    """
    Monitor and track timeout events across system operations.
    
    Features:
    - Timeout event tracking and statistics
    - Callback registration for timeout events
    - Historical timeout records maintenance
    """
    
    def __init__(self):
        self.timeouts: List[Dict[str, Any]] = []
        self.callbacks: List[Callable] = []
        self.config = TimeoutConfig()
        logger.info("timeout_monitor_initialized")
    
    def register_callback(self, callback: Callable[[str, float], None]):
        """Register callback function for timeout event notifications."""
        self.callbacks.append(callback)
    
    def on_timeout(self, task_id: str, timeout: float):
        """Record timeout event and trigger registered callbacks."""
        event = {
            "task_id": task_id,
            "timeout": timeout,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.timeouts.append(event)
        
        if len(self.timeouts) > 100:
            self.timeouts = self.timeouts[-100:]
        
        for callback in self.callbacks:
            try:
                callback(task_id, timeout)
            except Exception as e:
                logger.error(f"timeout_callback_error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get timeout event statistics and monitoring data."""
        if not self.timeouts:
            return {
                "total_timeouts": 0,
                "recent_timeouts": 0
            }
        
        recent = self.timeouts[-10:]
        
        return {
            "total_timeouts": len(self.timeouts),
            "recent_timeouts": len(recent),
            "avg_timeout": sum(e["timeout"] for e in recent) / len(recent) if recent else 0,
            "last_timeout": self.timeouts[-1] if self.timeouts else None
        }
