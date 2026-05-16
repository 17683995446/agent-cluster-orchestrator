from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Tuple
from datetime import datetime, timedelta
import asyncio
import structlog

logger = structlog.get_logger()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using sliding window algorithm."""
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst_size: int = 10
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self._request_counts: Dict[str, Tuple[datetime, int]] = {}
        self._lock = asyncio.Lock()
    
    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        key = f"rate_limit:{client_ip}"
        
        async with self._lock:
            now = datetime.utcnow()
            window_start = now - timedelta(minutes=1)
            
            if key in self._request_counts:
                last_request, count = self._request_counts[key]
                
                if last_request < window_start:
                    self._request_counts[key] = (now, 1)
                else:
                    if count >= self.requests_per_minute:
                        logger.warning(
                            "rate_limit_exceeded",
                            client_ip=client_ip,
                            count=count
                        )
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Rate limit exceeded. Please try again later."
                        )
                    self._request_counts[key] = (now, count + 1)
            else:
                self._request_counts[key] = (now, 1)
        
        response = await call_next(request)
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class CircuitBreaker:
    """Circuit breaker pattern implementation for external service calls."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self._failure_count = 0
        self._last_failure_time: datetime | None = None
        self._state = "closed"
    
    @property
    def state(self) -> str:
        now = datetime.utcnow()
        
        if self._state == "open":
            if self._last_failure_time:
                elapsed = (now - self._last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self._state = "half-open"
                    logger.info("circuit_breaker_half_open")
        
        return self._state
    
    def call(self, func, *args, **kwargs):
        if self.state == "open":
            logger.warning("circuit_breaker_open", func=func.__name__)
            raise Exception("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    async def call_async(self, func, *args, **kwargs):
        if self.state == "open":
            logger.warning("circuit_breaker_open", func=func.__name__)
            raise Exception("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        self._failure_count = 0
        if self._state == "half-open":
            self._state = "closed"
            logger.info("circuit_breaker_closed")
    
    def _on_failure(self):
        self._failure_count += 1
        self._last_failure_time = datetime.utcnow()
        
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning("circuit_breaker_opened", failure_count=self._failure_count)


circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60
)
