# Agent Cluster Orchestrator - Developer Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Architecture Overview](#architecture-overview)
3. [Development Setup](#development-setup)
4. [API Reference](#api-reference)
5. [Testing](#testing)
6. [Deployment](#deployment)

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+

### Quick Start

```bash
# Clone repository
git clone https://github.com/your-org/agent-cluster-orchestrator.git
cd agent-cluster-orchestrator

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install

# Start services
docker-compose up -d postgres redis

# Run backend
cd ../backend
uvicorn app.main:app --reload

# Run frontend (new terminal)
cd ../frontend
npm run dev
```

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────┐
│                   Client Applications               │
│         (Web Dashboard, CLI, SDK, API)             │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                   FastAPI Gateway                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │  Auth    │ │  Rate    │ │   WebSocket      │   │
│  │  Service │ │  Limiter │ │   Manager        │   │
│  └──────────┘ └──────────┘ └──────────────────┘   │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                 Service Layer                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │  Agent   │ │  Task    │ │    Cluster       │   │
│  │  Service │ │  Service │ │    Orchestrator  │   │
│  └──────────┘ └──────────┘ └──────────────────┘   │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│               Async Execution Layer                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │  Celery  │ │  Redis   │ │   LLM Providers  │   │
│  │  Workers │ │  Broker  │ │   (OpenAI, etc)  │   │
│  └──────────┘ └──────────┘ └──────────────────┘   │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                    Data Layer                       │
│        PostgreSQL          │          Redis         │
│      (Persistent)         │       (Cache/Queue)   │
└───────────────────────────┴─────────────────────────┘
```

## Development Setup

### Environment Variables

Create `.env` files in backend and frontend directories:

**Backend (.env)**
```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/agent_cluster
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-min-32-chars
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional
SENTRY_DSN=https://...
JAEGER_ENDPOINT=http://localhost:14268/api/traces
```

**Frontend (.env)**
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

### Database Setup

```bash
# Create database
psql -U postgres -c "CREATE DATABASE agent_cluster;"

# Run migrations
alembic upgrade head

# Seed initial data (optional)
python scripts/seed_db.py
```

### Running Tests

```bash
# Unit tests
pytest backend/tests/unit -v

# Integration tests
pytest backend/tests/integration -v

# All tests with coverage
pytest backend/tests --cov=app --cov-report=html

# Frontend tests
cd frontend
npm test
```

## API Reference

### Authentication

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "password123"
}
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Agents

#### Create Agent
```http
POST /api/v1/agents
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "data-analyst",
  "capabilities": ["data_analysis", "visualization"],
  "model": "gpt-4",
  "provider": "openai",
  "max_concurrent_tasks": 5
}
```

#### List Agents
```http
GET /api/v1/agents?status=active&limit=20
Authorization: Bearer <token>
```

### Tasks

#### Create Task
```http
POST /api/v1/tasks
Authorization: Bearer <token>
Content-Type: application/json

{
  "description": "Analyze Q4 sales data",
  "type": "data_analysis",
  "priority": 1,
  "input_data": {
    "quarter": 4,
    "year": 2024
  },
  "required_capabilities": ["data_analysis"]
}
```

#### Get Task
```http
GET /api/v1/tasks/{task_id}
Authorization: Bearer <token>
```

## Testing

### Writing Tests

```python
# backend/tests/unit/test_agent_service.py
import pytest
from app.services.agent_lifecycle_management_service import AgentService

@pytest.fixture
def agent_service():
    return AgentService()

@pytest.mark.asyncio
async def test_create_agent(agent_service):
    agent = await agent_service.create_agent(
        name="test-agent",
        capabilities=["test"],
        model="gpt-4"
    )
    assert agent.id is not None
    assert agent.name == "test-agent"
```

### Test Fixtures

```python
# backend/tests/conftest.py
import pytest
import asyncio
from httpx import AsyncClient
from app.main import app

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

## Deployment

### Docker

```bash
# Build images
docker-compose build

# Run in production
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes

```bash
# Apply configurations
kubectl apply -f k8s/

# Check status
kubectl get pods -n agent-cluster

# View logs
kubectl logs -f deployment/api -n agent-cluster
```

### Monitoring

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
- **Jaeger**: http://localhost:16686

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.
