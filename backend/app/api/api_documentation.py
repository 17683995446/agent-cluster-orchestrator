"""
API Documentation and Examples for Agent Cluster Orchestrator.

This module provides comprehensive API documentation with examples
that can be used with OpenAPI/Swagger.
"""
from fastapi import APIRouter, Body
from pydantic import Field
from typing import List, Optional, Dict, Any
from app.schemas.agent_api_schemas import AgentCreate, AgentUpdate
from app.schemas.task_api_schemas import TaskCreate, ClusterExecuteRequest

router = APIRouter(prefix="/docs", tags=["Documentation"])

API_EXAMPLES = {
    "create_agent": {
        "summary": "Create a new agent",
        "description": "Register a new AI agent in the cluster with specified capabilities",
        "value": {
            "name": "data-analyst",
            "capabilities": ["data_analysis", "visualization", "sql_queries"],
            "model": "gpt-4",
            "provider": "openai",
            "max_concurrent_tasks": 5
        }
    },
    "create_task": {
        "summary": "Create a new task",
        "description": "Submit a new task for execution by an agent",
        "value": {
            "description": "Analyze sales data and generate report",
            "type": "analysis",
            "priority": 1,
            "input_data": {
                "data_source": "sales_database",
                "analysis_type": "trend_analysis",
                "date_range": "2024-01-01 to 2024-12-31"
            },
            "required_capabilities": ["data_analysis"]
        }
    },
    "cluster_execution": {
        "summary": "Execute cluster task",
        "description": "Execute a complex task across multiple agents",
        "value": {
            "description": "Comprehensive market analysis",
            "subtasks": [
                {
                    "description": "Collect competitor data",
                    "required_capabilities": ["web_scraping", "data_collection"],
                    "priority": 1
                },
                {
                    "description": "Analyze pricing trends",
                    "required_capabilities": ["data_analysis"],
                    "priority": 2
                },
                {
                    "description": "Generate executive summary",
                    "required_capabilities": ["report_generation"],
                    "priority": 3
                }
            ]
        }
    }
}

@router.get("/examples")
async def get_api_examples() -> Dict[str, Any]:
    """
    Get all API request examples.
    
    Returns comprehensive examples for all major API endpoints
    including agent management, task execution, and cluster orchestration.
    """
    return {
        "version": "2.0",
        "examples": API_EXAMPLES,
        "schemas": {
            "agent_capabilities": [
                "code_generation",
                "code_review",
                "data_analysis",
                "text_generation",
                "translation",
                "summarization",
                "question_answering",
                "web_scraping",
                "api_integration"
            ],
            "task_types": [
                "code_generation",
                "code_review",
                "data_analysis",
                "text_generation",
                "question_answering",
                "cluster_execution"
            ],
            "task_priorities": {
                "0": "low - Background processing",
                "1": "normal - Standard processing",
                "2": "high - Priority processing",
                "3": "urgent - Immediate processing"
            }
        }
    }

@router.get("/workflows")
async def get_workflows() -> Dict[str, Any]:
    """
    Get common API workflows and patterns.
    
    Returns step-by-step workflows for typical use cases.
    """
    return {
        "workflows": {
            "simple_agent_task": {
                "title": "Simple Agent Task Execution",
                "steps": [
                    {
                        "step": 1,
                        "action": "Create Agent",
                        "endpoint": "POST /api/v1/agents",
                        "example": API_EXAMPLES["create_agent"]
                    },
                    {
                        "step": 2,
                        "action": "Create Task",
                        "endpoint": "POST /api/v1/tasks",
                        "example": API_EXAMPLES["create_task"]
                    },
                    {
                        "step": 3,
                        "action": "Monitor Task",
                        "endpoint": "GET /api/v1/tasks/{task_id}",
                        "description": "Poll or use WebSocket for status updates"
                    }
                ]
            },
            "cluster_task": {
                "title": "Complex Cluster Task",
                "steps": [
                    {
                        "step": 1,
                        "action": "Create Multiple Agents",
                        "endpoint": "POST /api/v1/agents (multiple calls)",
                        "description": "Create agents with complementary capabilities"
                    },
                    {
                        "step": 2,
                        "action": "Submit Cluster Task",
                        "endpoint": "POST /api/v1/cluster/execute",
                        "example": API_EXAMPLES["cluster_execution"]
                    },
                    {
                        "step": 3,
                        "action": "Monitor Progress",
                        "endpoint": "WebSocket /api/v1/ws/stream",
                        "description": "Real-time updates on subtask progress"
                    },
                    {
                        "step": 4,
                        "action": "Get Results",
                        "endpoint": "GET /api/v1/tasks/{cluster_task_id}",
                        "description": "Retrieve aggregated results"
                    }
                ]
            }
        }
    }

@router.get("/best_practices")
async def get_best_practices() -> Dict[str, Any]:
    """
    Get API best practices and recommendations.
    """
    return {
        "authentication": {
            "method": "Bearer Token (JWT)",
            "header": "Authorization: Bearer <token>",
            "endpoints": {
                "login": "POST /api/v1/auth/login",
                "refresh": "POST /api/v1/auth/refresh",
                "me": "GET /api/v1/auth/me"
            },
            "recommendations": [
                "Use HTTPS in production",
                "Store tokens securely",
                "Implement token refresh before expiration",
                "Use short-lived access tokens (30 min)",
                "Use longer-lived refresh tokens (7 days)"
            ]
        },
        "rate_limiting": {
            "default_limit": "60 requests per minute",
            "headers": {
                "X-RateLimit-Limit": "Requests allowed per window",
                "X-RateLimit-Remaining": "Remaining requests in window",
                "X-RateLimit-Reset": "Unix timestamp when limit resets"
            },
            "recommendations": [
                "Implement exponential backoff for retries",
                "Cache responses when appropriate",
                "Use WebSocket for real-time updates instead of polling",
                "Batch requests when possible"
            ]
        },
        "error_handling": {
            "error_format": {
                "code": "ERROR_CODE",
                "message": "Human readable message",
                "details": {},
                "timestamp": "2024-01-01T00:00:00Z",
                "path": "/api/v1/endpoint"
            },
            "common_error_codes": {
                "RESOURCE_NOT_FOUND": "404 - Agent or task not found",
                "VALIDATION_ERROR": "422 - Invalid request data",
                "RATE_LIMIT_EXCEEDED": "429 - Too many requests",
                "INTERNAL_ERROR": "500 - Server error"
            }
        },
        "performance": {
            "recommendations": [
                "Use pagination for list endpoints (max 100 items)",
                "Enable response caching for read operations",
                "Use WebSocket for real-time updates",
                "Implement request batching for bulk operations",
                "Use async processing for long-running tasks"
            ]
        }
    }

@router.get("/sdk_examples/{language}")
async def get_sdk_examples(language: str) -> Dict[str, Any]:
    """
    Get SDK examples for different programming languages.
    
    Supported languages: python, typescript, javascript
    """
    examples = {
        "python": {
            "installation": "pip install agent-cluster-sdk",
            "authentication": '''
from agent_cluster_sdk import Client

client = Client(base_url="https://api.example.com")
client.auth.login(username="user", password="pass")
token = client.auth.get_token()
''',
            "create_agent": '''
agent = client.agents.create(
    name="my-agent",
    capabilities=["code_generation"],
    model="gpt-4"
)
print(f"Created agent: {agent.id}")
''',
            "create_task": '''
task = client.tasks.create(
    description="Generate Python web scraper",
    type="code_generation",
    priority=1
)
print(f"Task created: {task.id}")
''',
            "websocket": '''
import asyncio
from agent_cluster_sdk import WebSocketClient

async def handle_message(message):
    print(f"Received: {message}")

client = WebSocketClient("wss://api.example.com/ws")
await client.connect()
await client.subscribe("tasks")
client.on_message(handle_message)
await asyncio.sleep(60)
'''
        },
        "typescript": {
            "installation": "npm install agent-cluster-sdk",
            "authentication": '''
import { Client } from 'agent-cluster-sdk';

const client = new Client({ baseUrl: 'https://api.example.com' });
await client.auth.login({ username: 'user', password: 'pass' });
const token = await client.auth.getToken();
''',
            "create_agent": '''
const agent = await client.agents.create({
  name: 'my-agent',
  capabilities: ['code_generation'],
  model: 'gpt-4'
});
console.log(`Created agent: ${agent.id}`);
''',
            "create_task": '''
const task = await client.tasks.create({
  description: 'Generate Python web scraper',
  type: 'code_generation',
  priority: 1
});
console.log(`Task created: ${task.id}`);
''',
            "websocket": '''
import { WebSocketClient } from 'agent-cluster-sdk';

const client = new WebSocketClient('wss://api.example.com/ws');
await client.connect();
await client.subscribe('tasks');
client.onMessage((message) => {
  console.log('Received:', message);
});
'''
        }
    }
    
    if language.lower() not in examples:
        return {
            "error": f"Language '{language}' not supported",
            "supported_languages": list(examples.keys())
        }
    
    return examples[language.lower()]
