"""
Cache Consistency Manager for Agent Cluster Orchestrator.
Provides cache invalidation and synchronization mechanisms.
"""
from __future__ import annotations

import asyncio
import hashlib
from abc import ABC, abstractmethod
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, Dict, Set, List, Awaitable
import structlog

logger = structlog.get_logger()


class CacheStrategy(Enum):
    """Cache consistency strategies."""
    CACHE_ASIDE = "cache_aside"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    REFRESH_AHEAD = "refresh_ahead"


class InvalidationEvent(Enum):
    """Types of cache invalidation events."""
    UPDATED = "updated"
    DELETED = "deleted"
    EXPIRED = "expired"


@dataclass
class CacheEntry:
    """Represents a cached value with metadata."""
    key: str
    value: Any
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    expires_at: Optional[float] = None
    version: int = 1
    tags: Set[str] = field(default_factory=set)
    
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now().timestamp() > self.expires_at


class LRUCache:
    """
    In-memory LRU cache with TTL support.
    """
    def __init__(self, max_size: int = 10000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        async with self.lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            
            if entry.is_expired():
                del self.cache[key]
                return None
            
            self.cache.move_to_end(key)
            return entry.value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: Optional[Set[str]] = None) -> None:
        async with self.lock:
            if key in self.cache:
                old_entry = self.cache[key]
                new_entry = CacheEntry(
                    key=key,
                    value=value,
                    version=old_entry.version + 1,
                    tags=tags or old_entry.tags,
                )
                if ttl:
                    new_entry.expires_at = datetime.now().timestamp() + ttl
                self.cache[key] = new_entry
                self.cache.move_to_end(key)
            else:
                entry = CacheEntry(
                    key=key,
                    value=value,
                    tags=tags or set(),
                )
                if ttl:
                    entry.expires_at = datetime.now().timestamp() + ttl
                self.cache[key] = entry
            
            # Evict if over capacity
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
    
    async def delete(self, key: str) -> bool:
        async with self.lock:
            if key not in self.cache:
                return False
            del self.cache[key]
        return True
    
    async def invalidate_tag(self, tag: str) -> int:
        """Invalidate all cache entries with a specific tag."""
        count = 0
        async with self.lock:
            keys_to_delete = [
                key for key, entry in self.cache.items() 
                if tag in entry.tags
            ]
            for key in keys_to_delete:
                del self.cache[key]
                count += 1
        return count
    
    async def clear(self) -> None:
        async with self.lock:
            self.cache.clear()


class ConsistentCacheManager:
    """
    Manages cache consistency with multi-level caching system.
    
    Features:
    - Multi-level caching (local + Redis)
    - Tag-based invalidation
    - Write-through/write-behind
    - Cache versioning
    - Event-driven invalidation
    """
    
    def __init__(self):
        self.local_cache = LRUCache()
        self._invalidation_callbacks: List[Callable[[str, InvalidationEvent], Awaitable[None]]] = []
        self._pending_writes: Dict[str, tuple[Any, float]] = {}
        self._write_lock = asyncio.Lock()
    
    def register_invalidation_callback(
        self, 
        callback: Callable[[str, InvalidationEvent], Awaitable[None]]
    ) -> None:
        self._invalidation_callbacks.append(callback)
    
    async def _notify_invalidation(self, key: str, event: InvalidationEvent) -> None:
        for callback in self._invalidation_callbacks:
            await callback(key, event)
    
    @asynccontextmanager
    async def cached_get(
        self,
        key: str,
        loader: Callable[[], Awaitable[Any]],
        ttl: int = 3600,
        tags: Optional[Set[str]] = None,
    ):
        """Get value, falling back to loader if not in cache."""
        value = await self.local_cache.get(key)
        if value is not None:
            yield value
            return
        
        value = await loader()
        
        if value is not None:
            await self.local_cache.set(key, value, ttl, tags)
        
        yield value
    
    async def cached_set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
        tags: Optional[Set[str]] = None,
        strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH,
    ) -> None:
        await self.local_cache.set(key, value, ttl, tags)
        
        if strategy == CacheStrategy.WRITE_THROUGH:
            await self._notify_invalidation(key, InvalidationEvent.UPDATED)
    
    async def invalidate(
        self,
        key: str,
        event: InvalidationEvent = InvalidationEvent.UPDATED,
    ) -> None:
        deleted = await self.local_cache.delete(key)
        if deleted:
            logger.debug(
                "cache_entry_invalidated",
                key=key,
                event=event.value,
            )
        await self._notify_invalidation(key, event)
    
    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with a specific tag."""
        count = await self.local_cache.invalidate_tag(tag)
        logger.debug(
            "cache_tag_invalidated",
            tag=tag,
            count=count,
        )
        return count
    
    async def clear(self) -> None:
        await self.local_cache.clear()
        logger.debug("cache_cleared")


class AgentCache:
    """
    Specialized cache management for Agent operations with advanced caching.
    """
    
    def __init__(self, cache_manager: ConsistentCacheManager):
        self.cache_manager = cache_manager
    
    @staticmethod
    def get_agent_key(agent_id: str) -> str:
        return f"agent:{agent_id}"
    
    @staticmethod
    def get_agent_list_key(filter_key: str = "all") -> str:
        return f"agents:list:{filter_key}"
    
    async def get_agent(
        self,
        agent_id: str,
        loader: Callable[[], Awaitable[Any]],
    ) -> Any:
        key = self.get_agent_key(agent_id)
        return await self.cache_manager.cached_get(
            key=key,
            loader=loader,
            ttl=300,
            tags={"agent", f"agent:{agent_id}"},
        )
    
    async def set_agent(
        self,
        agent_id: str,
        value: Any,
    ) -> None:
        key = self.get_agent_key(agent_id)
        await self.cache_manager.cached_set(
            key=key,
            value=value,
            ttl=300,
            tags={"agent", f"agent:{agent_id}"},
        )
    
    async def invalidate_agent(
        self,
        agent_id: str,
    ) -> None:
        await self.cache_manager.invalidate(self.get_agent_key(agent_id))
        await self.cache_manager.invalidate_by_tag("agents:list")


class TaskCache:
    """
    Specialized cache management for Task operations.
    """
    
    def __init__(self, cache_manager: ConsistentCacheManager):
        self.cache_manager = cache_manager
    
    @staticmethod
    def get_task_key(task_id: str) -> str:
        return f"task:{task_id}"
    
    @staticmethod
    def get_task_list_key(filter_key: str = "all") -> str:
        return f"tasks:list:{filter_key}"
    
    async def get_task(
        self,
        task_id: str,
        loader: Callable[[], Awaitable[Any]],
    ) -> Any:
        key = self.get_task_key(task_id)
        return await self.cache_manager.cached_get(
            key=key,
            loader=loader,
            ttl=60,  # Shorter TTL for tasks which change often
            tags={"task", f"task:{task_id}"},
        )
    
    async def set_task(
        self,
        task_id: str,
        value: Any,
    ) -> None:
        key = self.get_task_key(task_id)
        await self.cache_manager.cached_set(
            key=key,
            value=value,
            ttl=60,
            tags={"task", f"task:{task_id}"},
        )
    
    async def invalidate_task(
        self,
        task_id: str,
    ) -> None:
        await self.cache_manager.invalidate(self.get_task_key(task_id))
        await self.cache_manager.invalidate_by_tag("tasks:list")


# Global instances
_consistent_cache = ConsistentCacheManager()
agent_cache = AgentCache(_consistent_cache)
task_cache = TaskCache(_consistent_cache)
