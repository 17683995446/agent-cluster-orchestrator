from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from typing import Optional
import secrets
import structlog
from datetime import datetime, timedelta
import hashlib

logger = structlog.get_logger()

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyManager:
    """Manage API keys for authentication."""
    
    def __init__(self):
        self._keys: dict[str, dict] = {}
    
    def create_key(self, name: str, expires_in_days: int = 365) -> tuple[str, str]:
        """Create a new API key."""
        key = f"ack_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        expiry = datetime.utcnow() + timedelta(days=expires_in_days)
        
        self._keys[key_hash] = {
            "name": name,
            "created_at": datetime.utcnow(),
            "expires_at": expiry,
            "is_active": True,
            "rate_limit": 100
        }
        
        logger.info("api_key_created", name=name, expires_at=expiry.isoformat())
        return key, key_hash
    
    def validate_key(self, key: str) -> Optional[dict]:
        """Validate an API key."""
        if not key:
            return None
        
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        key_info = self._keys.get(key_hash)
        
        if not key_info:
            logger.warning("api_key_not_found", key_hash=key_hash[:8])
            return None
        
        if not key_info["is_active"]:
            logger.warning("api_key_inactive", name=key_info["name"])
            return None
        
        if datetime.utcnow() > key_info["expires_at"]:
            logger.warning("api_key_expired", name=key_info["name"])
            return None
        
        return key_info
    
    def revoke_key(self, key: str) -> bool:
        """Revoke an API key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        if key_hash in self._keys:
            self._keys[key_hash]["is_active"] = False
            logger.info("api_key_revoked", name=self._keys[key_hash]["name"])
            return True
        return False
    
    def list_keys(self) -> list[dict]:
        """List all API keys (without the actual key)."""
        return [
            {
                "name": info["name"],
                "created_at": info["created_at"].isoformat(),
                "expires_at": info["expires_at"].isoformat(),
                "is_active": info["is_active"]
            }
            for info in self._keys.values()
        ]


api_key_manager = APIKeyManager()


async def verify_api_key(
    request: Request,
    api_key: Optional[str] = Security(API_KEY_HEADER)
) -> Optional[dict]:
    """Dependency to verify API key."""
    if not api_key:
        return None
    
    key_info = api_key_manager.validate_key(api_key)
    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key"
        )
    
    return key_info


def require_api_key():
    """Dependency that requires API key authentication."""
    async def dependency(
        request: Request,
        api_key: Optional[str] = Security(API_KEY_HEADER)
    ) -> dict:
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required"
            )
        
        key_info = api_key_manager.validate_key(api_key)
        if not key_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key"
            )
        
        return key_info
    
    return dependency
