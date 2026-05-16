from typing import TypeVar, Generic, Optional, Callable, Any, Union, Dict, List
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel
import json
import hashlib
import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class CacheStrategy(str, Enum):
    CACHE_ASIDE = "cache_aside"
    WRITE_THROUGH = "write_through"
    READ_THROUGH = "read_through"
    REFRESH_AHEAD = "refresh_ahead"


class CacheEntry(BaseModel):
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    tags: List[str] = []
    version: int = 1
    hit_count: int = 0
    last_accessed: Optional[datetime] = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def access(self) -> None:
        self.hit_count += 1
        self.last_accessed = datetime.utcnow()


class CacheMetrics(BaseModel):
    hits: int = 0
    misses: int = 0
    writes: int = 0
    deletes: int = 0
    expirations: int = 0
    hit_rate: float = 0.0
    total_keys: int = 0
    memory_used_bytes: int = 0


class CacheKeyBuilder:
    @staticmethod
    def build(*parts: Any, prefix: str = "agent_cluster") -> str:
        cleaned_parts = [str(p) for p in parts if p is not None]
        key = ":".join([prefix] + cleaned_parts)
        return key

    @staticmethod
    def build_hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    @staticmethod
    def build_pattern(prefix: str, **kwargs) -> str:
        parts = [prefix]
        for k, v in sorted(kwargs.items()):
            if v is not None:
                parts.append(f"{k}:{v}")
        return ":".join(parts)


class MultiLayerCacheManager(Generic[T]):
    def __init__(
        self,
        redis_client,
        local_cache_size: int = 1000,
        default_ttl: int = 300,
        enable_metrics: bool = True
    ):
        self.redis = redis_client
        self.local_cache: Dict[str, CacheEntry] = {}
        self.local_cache_size = local_cache_size
        self.default_ttl = default_ttl
        self.enable_metrics = enable_metrics
        self.metrics = CacheMetrics()
        self._eviction_policy = "lru"

    async def get(
        self,
        key: str,
        deserializer: Optional[Callable[[bytes], T]] = None,
        fallback: Optional[Callable[[], T]] = None
    ) -> Optional[T]:
        if self.enable_metrics:
            self.metrics.misses += 1

        if key in self.local_cache:
            entry = self.local_cache[key]
            if not entry.is_expired():
                entry.access()
                self.metrics.hits += 1
                logger.debug("cache_hit_local", key=key, hit_count=entry.hit_count)
                return self._deserialize(entry.value, deserializer)
            else:
                del self.local_cache[key]
                self.metrics.expirations += 1

        try:
            cached_value = await self.redis.get(key)
            if cached_value:
                entry_data = json.loads(cached_value)
                entry = CacheEntry(**entry_data)
                if not entry.is_expired():
                    entry.access()
                    self._update_local_cache(key, entry)
                    self.metrics.hits += 1
                    logger.debug("cache_hit_redis", key=key)
                    return self._deserialize(entry.value, deserializer)
                else:
                    await self.redis.delete(key)
                    self.metrics.expirations += 1
        except Exception as e:
            logger.error("cache_get_error", key=key, error=str(e))

        if fallback:
            value = fallback()
            if value is not None:
                await self.set(key, value)
            return value

        return None

    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        if self.enable_metrics:
            self.metrics.writes += 1

        ttl = ttl or self.default_ttl
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            tags=tags or [],
            hit_count=0,
            last_accessed=datetime.utcnow()
        )

        try:
            serialized = json.dumps(entry.model_dump(), default=str)
            await self.redis.setex(key, ttl, serialized)
            self._update_local_cache(key, entry)
            logger.debug("cache_set", key=key, ttl=ttl)
            return True
        except Exception as e:
            logger.error("cache_set_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        if self.enable_metrics:
            self.metrics.deletes += 1

        try:
            if key in self.local_cache:
                del self.local_cache[key]
            await self.redis.delete(key)
            logger.debug("cache_delete", key=key)
            return True
        except Exception as e:
            logger.error("cache_delete_error", key=key, error=str(e))
            return False

    async def delete_pattern(self, pattern: str) -> int:
        count = 0
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                count = await self.redis.delete(*keys)
                self.local_cache = {
                    k: v for k, v in self.local_cache.items()
                    if not self._match_pattern(k, pattern)
                }
            logger.info("cache_delete_pattern", pattern=pattern, count=count)
        except Exception as e:
            logger.error("cache_delete_pattern_error", pattern=pattern, error=str(e))
        return count

    async def delete_by_tags(self, tags: List[str]) -> int:
        count = 0
        pattern = "*"
        try:
            keys_to_delete = []
            async for key in self.redis.scan_iter(match=pattern):
                cached_value = await self.redis.get(key)
                if cached_value:
                    entry_data = json.loads(cached_value)
                    entry = CacheEntry(**entry_data)
                    if any(tag in entry.tags for tag in tags):
                        keys_to_delete.append(key)
            if keys_to_delete:
                count = await self.redis.delete(*keys_to_delete)
                self.local_cache = {
                    k: v for k, v in self.local_cache.items()
                    if not any(tag in v.tags for tag in tags)
                }
            logger.info("cache_delete_by_tags", tags=tags, count=count)
        except Exception as e:
            logger.error("cache_delete_by_tags_error", tags=tags, error=str(e))
        return count

    async def exists(self, key: str) -> bool:
        try:
            if key in self.local_cache:
                if not self.local_cache[key].is_expired():
                    return True
                else:
                    del self.local_cache[key]
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error("cache_exists_error", key=key, error=str(e))
            return False

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], T],
        ttl: Optional[int] = None,
        deserializer: Optional[Callable[[bytes], T]] = None
    ) -> T:
        cached = await self.get(key, deserializer)
        if cached is not None:
            return cached

        value = compute_fn()
        if value is not None:
            await self.set(key, value, ttl)
        return value

    async def refresh(self, key: str, compute_fn: Callable[[], T]) -> Optional[T]:
        value = compute_fn()
        if value is not None:
            await self.set(key, value)
            logger.debug("cache_refresh", key=key)
        return value

    async def get_stats(self) -> CacheMetrics:
        try:
            info = await self.redis.info("memory")
            self.metrics.memory_used_bytes = info.get("used_memory", 0)
        except Exception:
            pass

        try:
            self.metrics.total_keys = await self.redis.dbsize()
        except Exception:
            pass

        total = self.metrics.hits + self.metrics.misses
        self.metrics.hit_rate = (self.metrics.hits / total * 100) if total > 0 else 0.0

        return self.metrics

    def _update_local_cache(self, key: str, entry: CacheEntry) -> None:
        if len(self.local_cache) >= self.local_cache_size:
            self._evict_lru()
        self.local_cache[key] = entry

    def _evict_lru(self) -> None:
        if not self.local_cache:
            return
        lru_key = min(
            self.local_cache.items(),
            key=lambda x: x[1].last_accessed or datetime.min
        )[0]
        del self.local_cache[lru_key]

    def _deserialize(self, value: Any, deserializer: Optional[Callable[[bytes], T]]) -> T:
        if deserializer:
            return deserializer(value)
        if isinstance(value, bytes):
            return json.loads(value)
        return value

    def _match_pattern(self, key: str, pattern: str) -> bool:
        import fnmatch
        return fnmatch.fnmatch(key, pattern)


class CacheAsideManager:
    def __init__(self, cache: MultiLayerCacheManager):
        self.cache = cache

    async def read(
        self,
        key: str,
        db_fetch_fn: Callable[[], T],
        ttl: Optional[int] = None
    ) -> T:
        cached = await self.cache.get(key)
        if cached is not None:
            return cached

        value = db_fetch_fn()
        if value is not None:
            await self.cache.set(key, value, ttl)
        return value

    async def write(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        return await self.cache.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        return await self.cache.delete(key)


class WriteThroughManager:
    def __init__(self, cache: MultiLayerCacheManager):
        self.cache = cache

    async def write(
        self,
        key: str,
        value: T,
        db_write_fn: Callable[[T], None],
        ttl: Optional[int] = None
    ) -> T:
        await db_write_fn(value)
        await self.cache.set(key, value, ttl)
        return value

    async def delete(
        self,
        key: str,
        db_delete_fn: Callable[[], None]
    ) -> bool:
        await db_delete_fn()
        return await self.cache.delete(key)


async def create_advanced_cache(redis_client, config: Optional[Dict[str, Any]] = None) -> MultiLayerCacheManager:
    config = config or {}
    return MultiLayerCacheManager(
        redis_client=redis_client,
        local_cache_size=config.get("local_cache_size", 1000),
        default_ttl=config.get("default_ttl", 300),
        enable_metrics=config.get("enable_metrics", True)
    )
