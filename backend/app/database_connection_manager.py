from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import os

def get_database_url() -> str:
    """Get database URL from settings or environment."""
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    try:
        from app.application_configuration import settings
        return settings.DATABASE_URL
    except:
        return "sqlite+aiosqlite:///./test.db"

def create_engine_and_session(url: Optional[str] = None):
    """Create database engine and session factory."""
    db_url = url or get_database_url()
    
    if db_url.startswith("sqlite"):
        engine = create_async_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    else:
        engine = create_async_engine(
            db_url,
            echo=False,
            poolclass=AsyncAdaptedQueuePool,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    return engine, async_session_factory

engine, async_session_factory = create_engine_and_session()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initialize database tables."""
    from app.models.agent_data_model import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    """Close database connections."""
    await engine.dispose()
