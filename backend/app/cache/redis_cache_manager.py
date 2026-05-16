import redis.asyncio as redis
from typing import Optional, Any, Union
import json
import structlog
from functools import wraps

logger = logger = structlog.get_logger()

class RedisCacheManager:
    """Redis cache manager with async support."""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self, redis_url: str):
        """Connect to Redis server."""
        try:
            self._client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )
            await self._client.ping()
            self._connected = True
            logger.info("redis_connected", url=redis_url)
        except Exception as e:
            logger.warning("redis_connection_failed", error=str(e))
            self._connected = False
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("redis_disconnected")
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.is_connected:
            return None
        try:
            value = await self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("cache_get_error", key=key, error=str(e))
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: int = 300
    ) -> bool:
        """Set value in cache with expiration."""
        if not self.is_connected:
            return False
        try:
            serialized = json.dumps(value, default=str)
            await self._client.set(key, serialized, ex=expire)
            return True
        except Exception as e:
            logger.error("cache_set_error", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.is_connected:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.error("cache_delete_error", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.is_connected:
            return False
        try:
            return await self._client.exists(key) > 0
        except Exception as e:
            logger.error("cache_exists_error", key=key, error=str(e))
            return False
    
    async def get_or_set(
        self,
        key: str,
        factory: callable,
        expire: int = 300
    ) -> Any:
        """Get from cache or set using factory function."""
        cached = await self.get(key)
        if cached is not None:
            return cached
        
        value = await factory()
        await self.set(key, value, expire)
        return value
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        if not self.is_connected:
            return 0
        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                return await self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.error("cache_invalidate_pattern_error", pattern=pattern, error=str(e))
            return 0
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter in cache."""
        if not self.is_connected:
            return None
        try:
            return await self._client.incrby(key, amount)
        except Exception as e:
            logger.error("cache_increment_error", key=key, error=str(e))
            return None
    
    async def get_json(self, key: str) -> Optional[dict]:
        """Get JSON object from cache."""
        return await self.get(key)
    
    async def set_json(
        self,
        key: str,
        value: dict,
        expire: int = 300
    ) -> bool:
        """Set JSON object in cache."""
        return await self.set(key, value, expire)

cache_manager = RedisCacheManager()


def cached(key_prefix: str, expire: int = 300):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{':'.join(str(a) for a in args)}"
            
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug("cache_hit", key=cache_key)
                return cached_value
            
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, expire)
            logger.debug("cache_miss", key=cache_key)
            
            return result
        return wrapper
    return decorator


class CacheKeys:
    """Cache key generators."""
    
    @staticmethod
    def agent(agent_id: str) -> str:
        return f"agent:{agent_id}"
    
    @staticmethod
    def agent_stats() -> str:
        return "agents:stats"
    
    @staticmethod
    def task(task_id: str) -> str:
        return f"task:{task_id}"
    
    @staticmethod
    def cluster_stats() -> str:
        return "cluster:stats"
    
    @staticmethod
    def capabilities() -> str:
        return "agents:capabilities"
