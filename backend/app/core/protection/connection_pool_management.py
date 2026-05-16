"""
Agent Cluster Orchestrator - Connection Pool Management Module

Provides efficient connection pooling for databases and network resources.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, List, Set
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PoolConfig:
    """Configuration parameters for connection pool behavior."""
    min_size: int = 5
    max_size: int = 100
    max_idle_time: float = 300.0
    acquire_timeout: float = 10.0
    health_check_interval: float = 60.0


class PoolExhaustedError(Exception):
    """Exception raised when connection pool reaches maximum capacity."""
    pass


class ConnectionWrapper:
    """Wrapper class for managed connections in connection pool."""
    
    def __init__(self, connection: Any, pool: 'ConnectionPool'):
        self.connection = connection
        self.pool = pool
        self.created_at = time.time()
        self.last_used_at = time.time()
        self.in_use = False
    
    async def __aenter__(self):
        self.in_use = True
        self.last_used_at = time.time()
        return self.connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.in_use = False
        await self.pool.release(self)


class ConnectionPool:
    """
    Connection pool for managing reusable database or network connections.
    
    Features:
    - Connection reuse optimization
    - Automatic connection health checking
    - Dynamic pool size management
    - Connection timeout handling
    """
    
    def __init__(self, config: PoolConfig, factory: Callable):
        self.config = config
        self.factory = factory
        self.available: List[ConnectionWrapper] = []
        self.acquired: Set[ConnectionWrapper] = set()
        self._lock = asyncio.Lock()
        self._closed = False
        logger.info("connection_pool_initialized", config=config)
    
    async def initialize(self):
        """Initialize connection pool with minimum configured connections."""
        async with self._lock:
            for _ in range(self.config.min_size):
                conn = await self.factory()
                wrapper = ConnectionWrapper(conn, self)
                self.available.append(wrapper)
        
        logger.info("connection_pool_initialized_connections", count=len(self.available))
    
    async def acquire(self) -> ConnectionWrapper:
        """Acquire connection from connection pool with timeout protection."""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        async with self._lock:
            while self.available:
                wrapper = self.available.pop(0)
                
                if await self._is_healthy(wrapper):
                    self.acquired.add(wrapper)
                    return wrapper
                else:
                    await self._close_connection(wrapper)
            
            total = len(self.available) + len(self.acquired)
            if total >= self.config.max_size:
                try:
                    await asyncio.wait_for(
                        self._wait_for_available(),
                        timeout=self.config.acquire_timeout
                    )
                except asyncio.TimeoutError:
                    raise PoolExhaustedError(
                        f"Connection pool exhausted, max_size={self.config.max_size}"
                    )
            else:
                conn = await self.factory()
                wrapper = ConnectionWrapper(conn, self)
                self.acquired.add(wrapper)
                return wrapper
        
        return await self.acquire()
    
    async def _wait_for_available(self):
        """Wait until connection becomes available in connection pool."""
        while not self.available:
            await asyncio.sleep(0.1)
    
    async def release(self, wrapper: ConnectionWrapper):
        """Release connection back to connection pool for reuse."""
        if wrapper not in self.acquired:
            return
        
        async with self._lock:
            self.acquired.discard(wrapper)
            
            if await self._should_close(wrapper):
                await self._close_connection(wrapper)
            else:
                wrapper.in_use = False
                self.available.append(wrapper)
    
    async def _is_healthy(self, wrapper: ConnectionWrapper) -> bool:
        """Check if connection is healthy and can be reused."""
        idle_time = time.time() - wrapper.last_used_at
        if idle_time > self.config.max_idle_time:
            return False
        
        return True
    
    async def _should_close(self, wrapper: ConnectionWrapper) -> bool:
        """Determine if connection should be closed instead of reused."""
        idle_time = time.time() - wrapper.last_used_at
        total = len(self.available) + len(self.acquired)
        
        if total > self.config.min_size and idle_time > self.config.max_idle_time:
            return True
        
        return False
    
    async def _close_connection(self, wrapper: ConnectionWrapper):
        """Close connection gracefully and clean up resources."""
        try:
            if hasattr(wrapper.connection, 'close'):
                wrapper.connection.close()
        except Exception as e:
            logger.warning(f"error_closing_connection: {e}")
    
    async def close(self):
        """Close connection pool and all associated connections."""
        self._closed = True
        
        async with self._lock:
            for wrapper in self.available + list(self.acquired):
                await self._close_connection(wrapper)
            
            self.available.clear()
            self.acquired.clear()
        
        logger.info("connection_pool_closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics for monitoring purposes."""
        return {
            "available": len(self.available),
            "acquired": len(self.acquired),
            "total": len(self.available) + len(self.acquired),
            "max_size": self.config.max_size,
            "utilization": (len(self.acquired) / self.config.max_size * 100) if self.config.max_size > 0 else 0
        }
