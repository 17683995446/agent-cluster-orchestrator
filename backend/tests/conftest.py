import pytest
import asyncio
import os
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create in-memory SQLite database for testing."""
    from app.models.agent_data_model import Base
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()

@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with mocked database."""
    from app.main_fastapi_application import app
    from app.database_connection_manager import get_db
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.fixture
async def sample_agent(client: AsyncClient) -> dict:
    """Create a sample agent for testing."""
    response = await client.post(
        "/api/v1/agents",
        json={
            "name": "Test Agent",
            "capabilities": ["code_generation", "writing"],
            "model": "gpt-4",
            "provider": "openai"
        }
    )
    return response.json()

@pytest.fixture
async def sample_task(client: AsyncClient) -> dict:
    """Create a sample task for testing."""
    response = await client.post(
        "/api/v1/tasks",
        json={
            "description": "Write a hello world program",
            "priority": 5
        }
    )
    return response.json()
