"""
Agent Cluster Orchestrator - Adaptive Queue Management Module

Provides intelligent adaptive queue with priority and backpressure control.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, List, Optional
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class QueueConfig:
    """Configuration parameters for adaptive queue behavior."""
    initial_capacity: int = 100
    max_capacity: int = 1000
    growth_factor: float = 1.5
    shrink_factor: float = 0.5


class QueueFullError(Exception):
    """Exception raised when queue reaches maximum capacity."""
    pass


class PriorityItem:
    """Wrapper class for items in priority queue system."""
    
    def __init__(self, priority: int, item: Any):
        self.priority = priority
        self.item = item
        self.created_at = time.time()
    
    def __lt__(self, other: 'PriorityItem'):
        return self.priority > other.priority


class AdaptiveQueue:
    """
    Intelligent adaptive queue with automatic scaling capabilities.
    
    Key Features:
    - Automatic capacity scaling (growth/shrink)
    - Priority-based item ordering
    - Backpressure control mechanism
    - Comprehensive statistics tracking
    """
    
    def __init__(self, config: Optional[QueueConfig] = None):
        self.config = config or QueueConfig()
        self.capacity = self.config.initial_capacity
        self.queue: List[PriorityItem] = []
        self.stats = {
            "enqueued": 0,
            "dequeued": 0,
            "rejected": 0,
            "growth_count": 0,
            "shrink_count": 0
        }
        self._lock = asyncio.Lock()
        logger.info("adaptive_queue_initialized", config=self.config)
    
    async def enqueue(
        self,
        item: Any,
        priority: int = 0
    ) -> bool:
        """
        Add item to adaptive queue with specified priority.
        
        Args:
            item: Data item to enqueue
            priority: Priority level (higher = process first)
            
        Returns:
            Boolean indicating successful enqueue operation
            
        Raises:
            QueueFullError: When queue is full and cannot grow further
        """
        async with self._lock:
            if len(self.queue) >= self.capacity:
                if self.capacity < self.config.max_capacity:
                    old_capacity = self.capacity
                    self.capacity = min(
                        int(self.capacity * self.config.growth_factor),
                        self.config.max_capacity
                    )
                    self.stats["growth_count"] += 1
                    logger.info(
                        "queue_grew",
                        old_capacity=old_capacity,
                        new_capacity=self.capacity
                    )
                else:
                    if self.queue:
                        lowest = self.queue[-1]
                        if lowest.priority < priority:
                            self.queue.pop()
                            self.stats["rejected"] += 1
                        else:
                            self.stats["rejected"] += 1
                            return False
                    else:
                        self.stats["rejected"] += 1
                        return False
            
            priority_item = PriorityItem(priority, item)
            self.queue.append(priority_item)
            self.queue.sort()
            self.stats["enqueued"] += 1
            
            return True
    
    async def dequeue(self) -> Optional[Any]:
        """
        Remove and return highest priority item from adaptive queue.
        
        Returns:
            Highest priority item or None if queue is empty
        """
        async with self._lock:
            if not self.queue:
                return None
            
            item = self.queue.pop(0)
            self.stats["dequeued"] += 1
            
            if (len(self.queue) < self.capacity * self.config.shrink_factor
                and self.capacity > self.config.initial_capacity):
                old_capacity = self.capacity
                self.capacity = max(
                    int(self.capacity * self.config.shrink_factor),
                    self.config.initial_capacity
                )
                self.stats["shrink_count"] += 1
                logger.info(
                    "queue_shrank",
                    old_capacity=old_capacity,
                    new_capacity=self.capacity
                )
            
            return item.item
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics for monitoring."""
        return {
            **self.stats,
            "current_size": len(self.queue),
            "capacity": self.capacity,
            "utilization": len(self.queue) / self.capacity * 100 if self.capacity > 0 else 0
        }
