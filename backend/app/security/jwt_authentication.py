from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
import structlog
import secrets
import hashlib

logger = structlog.get_logger()

class JWTManager:
    """JWT token generation and validation."""
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7
    ):
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using salted SHA-256."""
        salt = secrets.token_hex(16)
        salted_password = salt + password
        hashed = hashlib.sha256(salted_password.encode()).hexdigest()
        return f"{salt}${hashed}"
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        try:
            salt, stored_hash = hashed_password.split("$", 1)
            salted_password = salt + plain_password
            computed_hash = hashlib.sha256(salted_password.encode()).hexdigest()
            return computed_hash == stored_hash
        except Exception:
            return False
    
    def create_access_token(
        self,
        subject: str,
        username: str,
        role: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> tuple[str, datetime]:
        """
        Create a JWT access token.
        
        Returns:
            tuple: (token, expiration_time)
        """
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": subject,
            "username": username,
            "role": role,
            "type": "access",
            "iat": now,
            "exp": expire
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.info(
            "access_token_created",
            subject=subject,
            username=username,
            expires_at=expire.isoformat()
        )
        
        return token, expire
    
    def create_refresh_token(
        self,
        subject: str,
        username: str
    ) -> tuple[str, datetime]:
        """
        Create a JWT refresh token.
        
        Returns:
            tuple: (token, expiration_time)
        """
        now = datetime.utcnow()
        expire = now + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": subject,
            "username": username,
            "type": "refresh",
            "iat": now,
            "exp": expire
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.info(
            "refresh_token_created",
            subject=subject,
            username=username,
            expires_at=expire.isoformat()
        )
        
        return token, expire
    
    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and validate a JWT token.
        
        Returns:
            dict: Token payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("token_expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("token_invalid", error=str(e))
            return None
    
    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify an access token."""
        payload = self.decode_token(token)
        if payload and payload.get("type") == "access":
            return payload
        return None
    
    def verify_refresh_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a refresh token."""
        payload = self.decode_token(token)
        if payload and payload.get("type") == "refresh":
            return payload
        return None


jwt_manager = JWTManager()
