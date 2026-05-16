from sqlalchemy import String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.models.agent_data_model import Base
from enum import Enum
import hashlib
import secrets

class UserRoleEnum(str, Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRoleEnum] = mapped_column(
        SQLEnum(UserRoleEnum, native_enum=False),
        default=UserRoleEnum.USER,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    last_login: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    @staticmethod
    def _get_salt() -> str:
        """Generate a secure salt."""
        return secrets.token_hex(16)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using SHA-256 with salt (simple but secure enough for demo)."""
        salt = User._get_salt()
        salted_password = salt + password
        hashed = hashlib.sha256(salted_password.encode()).hexdigest()
        return f"{salt}${hashed}"
    
    def verify_password(self, password: str) -> bool:
        """Verify a password against its hash."""
        try:
            salt, stored_hash = self.hashed_password.split("$", 1)
            salted_password = salt + password
            computed_hash = hashlib.sha256(salted_password.encode()).hexdigest()
            return computed_hash == stored_hash
        except Exception:
            return False
