from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from datetime import datetime

from app.database_connection_manager import get_db
from app.models.user_data_model import User
from app.schemas.authentication_schemas import (
    UserCreate, UserResponse, UserUpdate, LoginRequest, TokenResponse,
    RefreshTokenRequest, PasswordChange
)
from app.security.jwt_authentication import jwt_manager
from app.security.api_key_authentication import require_api_key
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user."""
    existing = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    if user_data.email:
        existing_email = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if existing_email.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    user = User(
        id=str(uuid.uuid4()),
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=jwt_manager.hash_password(user_data.password),
        role=user_data.role.value if hasattr(user_data.role, 'value') else user_data.role,
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    logger.info("user_registered", user_id=user.id, username=user.username)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if hasattr(user.role, 'value') else user.role,
        is_active=user.is_active,
        created_at=user.created_at
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return tokens."""
    result = await db.execute(
        select(User).where(User.username == login_data.username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not jwt_manager.verify_password(
        login_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    user.last_login = datetime.utcnow()
    await db.commit()
    
    access_token, access_expire = jwt_manager.create_access_token(
        subject=user.id,
        username=user.username,
        role=user.role.value if hasattr(user.role, 'value') else user.role
    )
    
    refresh_token, refresh_expire = jwt_manager.create_refresh_token(
        subject=user.id,
        username=user.username
    )
    
    logger.info("user_logged_in", user_id=user.id, username=user.username)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=jwt_manager.access_token_expire_minutes * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    payload = jwt_manager.verify_refresh_token(refresh_data.refresh_token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    access_token, access_expire = jwt_manager.create_access_token(
        subject=user.id,
        username=user.username,
        role=user.role.value if hasattr(user.role, 'value') else user.role
    )
    
    refresh_token, refresh_expire = jwt_manager.create_refresh_token(
        subject=user.id,
        username=user.username
    )
    
    logger.info("tokens_refreshed", user_id=user.id)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=jwt_manager.access_token_expire_minutes * 60
    )


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: dict = Depends(require_api_key()),
    db: AsyncSession = Depends(get_db)
):
    """Change user password."""
    result = await db.execute(
        select(User).where(User.id == current_user.get("sub"))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not jwt_manager.verify_password(
        password_data.old_password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password"
        )
    
    user.hashed_password = jwt_manager.hash_password(password_data.new_password)
    user.updated_at = datetime.utcnow()
    await db.commit()
    
    logger.info("password_changed", user_id=user.id)
    
    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: dict = Depends(require_api_key()),
    db: AsyncSession = Depends(get_db)
):
    """Get current user information."""
    result = await db.execute(
        select(User).where(User.id == current_user.get("sub"))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if hasattr(user.role, 'value') else user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login
    )
