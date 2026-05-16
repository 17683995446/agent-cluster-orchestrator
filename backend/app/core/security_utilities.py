"""
Security utilities and input validation.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
import re
import html
from urllib.parse import urlparse


class SecurityHeaders:
    """Security headers for HTTP responses."""
    
    @staticmethod
    def get_headers() -> dict:
        """Get security headers."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }


class InputValidator:
    """Input validation utilities."""
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input."""
        if not isinstance(value, str):
            return ""
        
        value = value.strip()
        value = html.escape(value)
        
        if len(value) > max_length:
            value = value[:max_length]
        
        return value
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal."""
        filename = filename.replace("..", "")
        filename = re.sub(r'[^\w\s.-]', '', filename)
        filename = filename.strip('. ')
        return filename[:255]
    
    @staticmethod
    def validate_id(id_value: Any) -> bool:
        """Validate ID format (UUID or integer)."""
        if isinstance(id_value, int):
            return id_value > 0
        
        if isinstance(id_value, str):
            uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            return bool(re.match(uuid_pattern, id_value, re.IGNORECASE))
        
        return False


class PasswordValidator:
    """Password strength validator."""
    
    @staticmethod
    def validate_strength(password: str) -> tuple[bool, list[str]]:
        """
        Validate password strength.
        Returns (is_valid, list_of_issues)
        """
        issues = []
        
        if len(password) < 8:
            issues.append("Password must be at least 8 characters long")
        
        if not re.search(r'[A-Z]', password):
            issues.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            issues.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', password):
            issues.append("Password must contain at least one digit")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            issues.append("Password must contain at least one special character")
        
        return len(issues) == 0, issues


class SQLInjectionProtector:
    """SQL injection protection utilities."""
    
    @staticmethod
    def is_safe_identifier(identifier: str) -> bool:
        """Check if identifier is safe for SQL queries."""
        if not identifier:
            return False
        
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
        return bool(re.match(pattern, identifier))
    
    @staticmethod
    def sanitize_like_pattern(pattern: str) -> str:
        """Sanitize LIKE pattern to prevent LIKE injection."""
        pattern = pattern.replace('\\', '\\\\')
        pattern = pattern.replace('%', '\\%')
        pattern = pattern.replace('_', '\\_')
        return pattern


# Security configuration model
class SecurityConfig(BaseModel):
    """Security configuration."""
    
    SECRET_KEY_MIN_LENGTH: int = Field(default=32, description="Minimum secret key length")
    PASSWORD_MIN_LENGTH: int = Field(default=8, description="Minimum password length")
    MAX_LOGIN_ATTEMPTS: int = Field(default=5, description="Maximum login attempts before lockout")
    LOCKOUT_DURATION_MINUTES: int = Field(default=15, description="Account lockout duration")
    SESSION_TIMEOUT_MINUTES: int = Field(default=30, description="Session timeout")
    API_KEY_PREFIX: str = Field(default="ak_", description="API key prefix for identification")
    ALLOWED_HOSTS: list[str] = Field(default=["localhost", "127.0.0.1"], description="Allowed hosts")


# Global security config
security_config = SecurityConfig()
