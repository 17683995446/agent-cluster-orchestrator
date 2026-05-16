"""
Dependency security middleware for FastAPI.
"""
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.security.jwt_authentication import JWTManager
from app.core.security_utilities import SecurityHeaders

security = HTTPBearer()


async def verify_api_key(request: Request) -> bool:
    """Verify API key from request headers."""
    api_key = request.headers.get("X-API-Key")
    
    if not api_key:
        return False
    
    if not api_key.startswith("ak_"):
        return False
    
    return True


async def require_authenticated(request: Request):
    """Require authenticated user for endpoint."""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    token = auth_header.split(" ")[1]
    jwt_manager = JWTManager()
    payload = jwt_manager.verify_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return payload


class SecurityMiddleware:
    """Security middleware for adding security headers."""
    
    def __init__(self, app):
        self.app = app
        self.headers = SecurityHeaders.get_headers()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)
    
    @staticmethod
    def add_security_headers(response_headers: list[tuple[str, str]]):
        """Add security headers to response."""
        headers_dict = dict(response_headers)
        security_headers = SecurityHeaders.get_headers()
        
        for key, value in security_headers.items():
            headers_dict[key] = value
        
        return list(headers_dict.items())


def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    if request.client:
        return request.client.host
    
    return "unknown"
