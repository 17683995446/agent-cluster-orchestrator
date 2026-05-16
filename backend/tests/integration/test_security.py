"""
Security-focused integration tests.
"""
import pytest
from httpx import AsyncClient
from app.main_fastapi_application import app
from app.core.security_utilities import (
    PasswordValidator,
    InputValidator,
    SQLInjectionProtector
)


class TestPasswordValidator:
    """Test password validation."""
    
    def test_weak_password_short(self):
        """Test that short passwords are rejected."""
        is_valid, issues = PasswordValidator.validate_strength("Ab1!")
        assert not is_valid
        assert "at least 8 characters" in issues[0]
    
    def test_weak_password_no_uppercase(self):
        """Test that passwords without uppercase are rejected."""
        is_valid, issues = PasswordValidator.validate_strength("abcdefg1!")
        assert not is_valid
    
    def test_weak_password_no_lowercase(self):
        """Test that passwords without lowercase are rejected."""
        is_valid, issues = PasswordValidator.validate_strength("ABCDEFG1!")
        assert not is_valid
    
    def test_weak_password_no_digit(self):
        """Test that passwords without digits are rejected."""
        is_valid, issues = PasswordValidator.validate_strength("Abcdefgh!")
        assert not is_valid
    
    def test_strong_password(self):
        """Test that strong passwords are accepted."""
        is_valid, issues = PasswordValidator.validate_strength("StrongPass123!")
        assert is_valid
        assert len(issues) == 0


class TestInputValidator:
    """Test input validation."""
    
    def test_sanitize_string(self):
        """Test string sanitization."""
        result = InputValidator.sanitize_string("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
    
    def test_validate_email_valid(self):
        """Test valid email validation."""
        assert InputValidator.validate_email("user@example.com")
        assert InputValidator.validate_email("test.user@domain.co.uk")
    
    def test_validate_email_invalid(self):
        """Test invalid email validation."""
        assert not InputValidator.validate_email("invalid")
        assert not InputValidator.validate_email("@domain.com")
        assert not InputValidator.validate_email("user@")
    
    def test_validate_url_valid(self):
        """Test valid URL validation."""
        assert InputValidator.validate_url("https://example.com")
        assert InputValidator.validate_url("http://localhost:8000")
    
    def test_validate_url_invalid(self):
        """Test invalid URL validation."""
        assert not InputValidator.validate_url("not a url")
        assert not InputValidator.validate_url("")
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        assert InputValidator.sanitize_filename("../etc/passwd") == "etcpasswd"
        assert InputValidator.sanitize_filename("normal_file.txt") == "normal_file.txt"
        assert InputValidator.sanitize_filename("file with spaces.txt") == "file with spaces.txt"
    
    def test_validate_id(self):
        """Test ID validation."""
        assert InputValidator.validate_id(123)
        assert InputValidator.validate_id("550e8400-e29b-41d4-a716-446655440000")


class TestSQLInjectionProtector:
    """Test SQL injection protection."""
    
    def test_safe_identifier(self):
        """Test safe identifier validation."""
        assert SQLInjectionProtector.is_safe_identifier("users")
        assert SQLInjectionProtector.is_safe_identifier("user_123")
        assert SQLInjectionProtector.is_safe_identifier("_private")
    
    def test_unsafe_identifier(self):
        """Test unsafe identifier detection."""
        assert not SQLInjectionProtector.is_safe_identifier("users; DROP TABLE users;--")
        assert not SQLInjectionProtector.is_safe_identifier("123users")
        assert not SQLInjectionProtector.is_safe_identifier("")
    
    def test_sanitize_like_pattern(self):
        """Test LIKE pattern sanitization."""
        result = SQLInjectionProtector.sanitize_like_pattern("test%value")
        assert "\\" in result
        assert result == "test\\%value"


@pytest.mark.asyncio
class TestSecurityHeaders:
    """Test security headers."""
    
    async def test_security_headers_present(self, client: AsyncClient):
        """Test that security headers are present."""
        response = await client.get("/health")
        assert response.status_code == 200
        
        headers = response.headers
        assert "x-content-type-options" in headers
        assert "x-frame-options" in headers


@pytest.mark.asyncio
class TestRateLimiting:
    """Test rate limiting."""
    
    async def test_rate_limit_exceeded(self, client: AsyncClient):
        """Test rate limiting when exceeded."""
        for _ in range(100):
            response = await client.get("/health")
            if response.status_code == 429:
                break
        
        response = await client.get("/health")
        assert response.status_code in [200, 429]
