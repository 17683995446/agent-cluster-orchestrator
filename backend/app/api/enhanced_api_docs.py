"""
Enhanced API Documentation with Examples.
Provides comprehensive OpenAPI documentation with examples.
"""
from fastapi import APIRouter, FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse


api_docs_router = APIRouter(tags=["documentation"])


def custom_openapi(app: FastAPI):
    """
    Custom OpenAPI schema with enhanced documentation and examples.
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Agent Cluster Orchestrator API",
        version="2.0.0",
        description="""
# Agent Cluster Orchestrator API

## Overview

A powerful system for managing distributed AI agent clusters and orchestrating complex task workflows.

### Features

- 🔐 **Authentication**: JWT + API Key support
- 🔄 **Real-time Updates**: WebSocket connections
- 📊 **Metrics & Monitoring**: Prometheus + OpenTelemetry
- 🚀 **High Performance**: Async architecture
- 🛡️ **Robust Security**: Rate limiting, circuit breakers
- 📦 **Container Ready**: Docker + Kubernetes deployment

### Quick Start

1. Authenticate using `/api/v1/auth/login` to get a JWT token
2. Use the token in the Authorization header: `Bearer <token>`
3. Create agents with the required capabilities
4. Submit tasks and monitor progress via WebSocket
        """,
        routes=app.routes,
    )
    
    # Add tags to organize endpoints
    openapi_schema["tags"] = [
        {
            "name": "agents",
            "description": "Agent management - Create, update, delete, and query agents",
            "externalDocs": {
                "description": "Agent management guide",
                "url": "https://docs.example.com/agents",
            },
        },
        {
            "name": "tasks",
            "description": "Task management - Submit, monitor, and cancel tasks",
            "externalDocs": {
                "description": "Task management guide",
                "url": "https://docs.example.com/tasks",
            },
        },
        {
            "name": "cluster",
            "description": "Cluster orchestration - Execute complex multi-agent workflows",
        },
        {
            "name": "authentication",
            "description": "Authentication - JWT and API Key management",
        },
        {
            "name": "health",
            "description": "Health monitoring - System health and metrics",
        },
    ]
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT authentication - Use `/auth/login` to get a token",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API Key authentication - Admin only",
        },
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


@api_docs_router.get("/docs", include_in_schema=False)
async def get_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Agent Cluster Orchestrator API",
    )


@api_docs_router.get("/redoc", include_in_schema=False)
async def get_redoc_ui():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="Agent Cluster Orchestrator API",
    )


@api_docs_router.get("/docs/examples", include_in_schema=False)
async def get_examples():
    """
    Get comprehensive API usage examples in multiple languages.
    """
    examples = {
        "curl": {
            "login": """
curl -X POST https://api.example.com/api/v1/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{
    "username": "admin",
    "password": "secure123!"
  }'
""",
            "create_agent": """
curl -X POST https://api.example.com/api/v1/agents \\
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "data-analyst",
    "capabilities": ["data_analysis", "visualization"],
    "model": "gpt-4",
    "provider": "openai",
    "max_concurrent_tasks": 5
  }'
""",
            "create_task": """
curl -X POST https://api.example.com/api/v1/tasks \\
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "description": "Analyze Q4 sales data",
    "type": "data_analysis",
    "priority": 1,
    "input_data": {
      "quarter": 4,
      "year": 2024,
      "region": "APAC"
    },
    "required_capabilities": ["data_analysis", "visualization"]
  }'
""",
        },
        "python": """
from agent_cluster_sdk import Client

# Initialize client
client = Client(
    base_url="https://api.example.com",
    api_key="ak_your_api_key",
)

# Authenticate
token = client.auth.login(
    username="admin",
    password="secure123!",
)

# Create agent
agent = client.agents.create(
    name="data-analyst",
    capabilities=["data_analysis", "visualization"],
    model="gpt-4",
    provider="openai",
    max_concurrent_tasks=5,
)

# Create task
task = client.tasks.create(
    description="Analyze Q4 sales data",
    type="data_analysis",
    priority=1,
    input_data={
        "quarter": 4,
        "year": 2024,
        "region": "APAC",
    },
)

# Poll for completion
while task.status not in ["completed", "failed"]:
    task = client.tasks.get(task.id)
    print(f"Status: {task.status} ({task.progress}%)")
    import time
    time.sleep(2)

# Get result
result = client.tasks.get_result(task.id)
print(f"Result: {result}")
""",
        "javascript": """
import { AgentClusterClient } from 'agent-cluster-sdk';

// Initialize client
const client = new AgentClusterClient({
  baseUrl: 'https://api.example.com',
});

// Login
await client.auth.login('admin', 'secure123!');

// Create agent
const agent = await client.agents.create({
  name: 'data-analyst',
  capabilities: ['data_analysis', 'visualization'],
  model: 'gpt-4',
  provider: 'openai',
});

// Create task
const task = await client.tasks.create({
  description: 'Analyze Q4 sales data',
  type: 'data_analysis',
  priority: 1,
  inputData: {
    quarter: 4,
    year: 2024,
    region: 'APAC',
  },
});

// Monitor via WebSocket
client.websocket.on('task_completed', (message) => {
  if (message.data.taskId === task.id) {
    console.log('Task completed!', message.data);
  }
});

await client.websocket.connect();
""",
    }
    
    return JSONResponse(examples)


def setup_api_docs(app: FastAPI):
    """
    Setup enhanced API documentation for FastAPI app.
    """
    app.openapi = lambda: custom_openapi(app)
    app.include_router(api_docs_router)
