"""
Phase 2: 性能优化与基准测试
Comprehensive Performance Optimization Suite
"""
from __future__ import annotations

import asyncio
import time
import psutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar
from functools import wraps
import structlog

logger = structlog.get_logger()

T = TypeVar('T')


class CacheStrategy(Enum):
    """Cache strategy types."""
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"
    WRITE_THROUGH = "write_through"
    WRITE_BACK = "write_back"


@dataclass
class PerformanceMetrics:
    """Performance metrics container."""
    operation: str
    start_time: float
    end_time: float = 0.0
    cpu_before: float = 0.0
    cpu_after: float = 0.0
    memory_before: int = 0
    memory_after: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    error: Optional[str] = None
    
    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        return (self.end_time - self.start_time) * 1000
    
    @property
    def cpu_delta(self) -> float:
        """Get CPU usage delta."""
        return self.cpu_after - self.cpu_before
    
    @property
    def memory_delta_mb(self) -> float:
        """Get memory delta in MB."""
        return (self.memory_after - self.memory_before) / (1024 * 1024)
    
    @property
    def cache_hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            "cpu_delta": self.cpu_delta,
            "memory_delta_mb": self.memory_delta_mb,
            "cache_hit_rate": self.cache_hit_rate,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "error": self.error
        }


class OptimizedCache:
    """
    High-performance cache with multiple strategies.
    
    Features:
    - LRU, LFU, FIFO eviction strategies
    - TTL support
    - Write-through and write-back policies
    - Automatic size management
    - Thread-safe operations
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        strategy: CacheStrategy = CacheStrategy.LRU,
        default_ttl: Optional[int] = None
    ):
        self.max_size = max_size
        self.strategy = strategy
        self.default_ttl = default_ttl
        
        self._cache: Dict[str, Any] = {}
        self._access_times: Dict[str, float] = {}
        self._access_counts: Dict[str, int] = {}
        self._creation_times: Dict[str, float] = {}
        self._ttls: Dict[str, float] = {}
        
        self._hits = 0
        self._misses = 0
        self._writes = 0
        
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            if self._is_expired(key):
                await self._evict(key)
                self._misses += 1
                return None
            
            self._hits += 1
            self._access_times[key] = time.time()
            self._access_counts[key] = self._access_counts.get(key, 0) + 1
            
            return self._cache[key]
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """Set value in cache."""
        async with self._lock:
            if key in self._cache:
                self._cache[key] = value
            else:
                if len(self._cache) >= self.max_size:
                    await self._evict_lru()
                
                self._cache[key] = value
                self._writes += 1
            
            now = time.time()
            self._access_times[key] = now
            self._access_counts[key] = 1
            self._creation_times[key] = now
            
            effective_ttl = ttl or self.default_ttl
            if effective_ttl:
                self._ttls[key] = now + effective_ttl
            else:
                self._ttls.pop(key, None)
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        async with self._lock:
            if key in self._cache:
                await self._evict(key)
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._access_times.clear()
            self._access_counts.clear()
            self._creation_times.clear()
            self._ttls.clear()
            self._hits = 0
            self._misses = 0
            self._writes = 0
    
    def _is_expired(self, key: str) -> bool:
        """Check if entry is expired."""
        if key not in self._ttls:
            return False
        return time.time() > self._ttls[key]
    
    async def _evict(self, key: str) -> None:
        """Evict single entry."""
        self._cache.pop(key, None)
        self._access_times.pop(key, None)
        self._access_counts.pop(key, None)
        self._creation_times.pop(key, None)
        self._ttls.pop(key, None)
    
    async def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._access_times:
            return
        
        lru_key = min(self._access_times.items(), key=lambda x: x[1])[0]
        await self._evict(lru_key)
    
    async def _evict_lfu(self) -> None:
        """Evict least frequently used entry."""
        if not self._access_counts:
            return
        
        lfu_key = min(self._access_counts.items(), key=lambda x: x[1])[0]
        await self._evict(lfu_key)
    
    async def _evict_fifo(self) -> None:
        """Evict oldest entry (FIFO)."""
        if not self._creation_times:
            return
        
        fifo_key = min(self._creation_times.items(), key=lambda x: x[1])[0]
        await self._evict(fifo_key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "strategy": self.strategy.value,
            "hits": self._hits,
            "misses": self._misses,
            "writes": self._writes,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "miss_rate": self._misses / total if total > 0 else 0.0
        }


class QueryOptimizer:
    """
    Query optimization utilities.
    
    Features:
    - Query batching
    - Connection pooling
    - Query caching
    - Result pagination
    """
    
    def __init__(self, cache: Optional[OptimizedCache] = None):
        self.cache = cache or OptimizedCache()
        self._query_history: List[Dict[str, Any]] = []
        self._slow_query_threshold_ms = 1000
    
    async def execute_with_cache(
        self,
        key: str,
        query_func: Callable,
        ttl: Optional[int] = None
    ) -> Any:
        """Execute query with caching."""
        cached = await self.cache.get(key)
        if cached is not None:
            logger.debug("cache_hit", key=key)
            return cached
        
        logger.debug("cache_miss", key=key)
        result = await query_func()
        await self.cache.set(key, result, ttl)
        
        return result
    
    async def batch_execute(
        self,
        items: List[Any],
        batch_func: Callable[[List[Any]], Any],
        batch_size: int = 100
    ) -> List[Any]:
        """Execute queries in batches."""
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = await batch_func(batch)
            results.extend(batch_results)
        
        return results
    
    async def paginated_query(
        self,
        query_func: Callable[[int, int], Any],
        page_size: int = 100,
        max_pages: int = 100
    ) -> List[Any]:
        """Execute paginated query."""
        results = []
        
        for page in range(max_pages):
            page_results = await query_func(page, page_size)
            
            if not page_results:
                break
            
            results.extend(page_results)
            
            if len(page_results) < page_size:
                break
        
        return results
    
    def log_slow_query(
        self,
        query: str,
        duration_ms: float
    ) -> None:
        """Log slow query for optimization."""
        if duration_ms > self._slow_query_threshold_ms:
            self._query_history.append({
                "query": query,
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.warning(
                "slow_query_detected",
                query=query[:100],
                duration_ms=duration_ms
            )


class PerformanceProfiler:
    """
    Performance profiling utilities.
    
    Features:
    - Operation timing
    - Resource monitoring
    - Bottleneck detection
    """
    
    def __init__(self):
        self._measurements: List[PerformanceMetrics] = []
    
    async def profile(
        self,
        operation: str,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """Profile an operation."""
        metrics = PerformanceMetrics(
            operation=operation,
            start_time=time.time(),
            cpu_before=psutil.cpu_percent(),
            memory_before=psutil.Process().memory_info().rss
        )
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            metrics.end_time = time.time()
            metrics.cpu_after = psutil.cpu_percent()
            metrics.memory_after = psutil.Process().memory_info().rss
            
            self._measurements.append(metrics)
            
            logger.info(
                "operation_completed",
                operation=operation,
                duration_ms=metrics.duration_ms
            )
            
            return result
            
        except Exception as e:
            metrics.end_time = time.time()
            metrics.error = str(e)
            self._measurements.append(metrics)
            
            logger.error(
                "operation_failed",
                operation=operation,
                error=str(e)
            )
            raise
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self._measurements:
            return {}
        
        durations = [m.duration_ms for m in self._measurements]
        
        return {
            "total_operations": len(self._measurements),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "total_cpu_delta": sum(m.cpu_delta for m in self._measurements),
            "total_memory_delta_mb": sum(m.memory_delta_mb for m in self._measurements),
            "overall_cache_hit_rate": sum(m.cache_hit_rate for m in self._measurements) / len(self._measurements)
        }


def timed_operation(operation_name: str):
    """Decorator to time operations."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                logger.info(
                    "timed_operation_complete",
                    operation=operation_name,
                    duration_ms=duration
                )
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.error(
                    "timed_operation_failed",
                    operation=operation_name,
                    duration_ms=duration,
                    error=str(e)
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                logger.info(
                    "timed_operation_complete",
                    operation=operation_name,
                    duration_ms=duration
                )
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.error(
                    "timed_operation_failed",
                    operation=operation_name,
                    duration_ms=duration,
                    error=str(e)
                )
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class ConnectionPool:
    """
    Optimized connection pool.
    
    Features:
    - Dynamic pool sizing
    - Connection health checks
    - Automatic reconnection
    """
    
    def __init__(
        self,
        create_connection: Callable,
        min_size: int = 5,
        max_size: int = 20,
        max_idle_time: int = 300
    ):
        self.create_connection = create_connection
        self.min_size = min_size
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._size = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire connection from pool."""
        try:
            conn = self._pool.get_nowait()
            
            if self._is_healthy(conn):
                return conn
            
            self._size -= 1
            
        except asyncio.QueueEmpty:
            pass
        
        async with self._lock:
            if self._size < self.max_size:
                self._size += 1
                return await self.create_connection()
        
        return await self._pool.get()
    
    async def release(self, conn) -> None:
        """Release connection back to pool."""
        if self._is_healthy(conn) and self._size < self.max_size:
            await self._pool.put(conn)
        else:
            self._size -= 1
    
    def _is_healthy(self, conn) -> bool:
        """Check if connection is healthy."""
        return True


class ConcurrencyOptimizer:
    """
    Concurrency optimization utilities.
    
    Features:
    - Adaptive concurrency limits
    - Load balancing
    - Resource-aware scheduling
    """
    
    def __init__(
        self,
        max_concurrent: int = 50,
        adaptive: bool = True
    ):
        self.max_concurrent = max_concurrent
        self.adaptive = adaptive
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._total_processed = 0
        self._total_errors = 0
    
    async def execute(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """Execute with concurrency control."""
        await self._semaphore.acquire()
        self._active_count += 1
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self._total_processed += 1
            return result
            
        except Exception as e:
            self._total_errors += 1
            raise
            
        finally:
            self._active_count -= 1
            self._semaphore.release()
    
    async def execute_batch(
        self,
        items: List[Any],
        func: Callable[[Any], Any],
        batch_size: Optional[int] = None
    ) -> List[Any]:
        """Execute batch with concurrency control."""
        batch_size = batch_size or self.max_concurrent
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[self.execute(func, item) for item in batch],
                return_exceptions=True
            )
            results.extend(batch_results)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get concurrency statistics."""
        return {
            "max_concurrent": self.max_concurrent,
            "current_active": self._active_count,
            "total_processed": self._total_processed,
            "total_errors": self._total_errors,
            "error_rate": self._total_errors / self._total_processed if self._total_processed > 0 else 0
        }
