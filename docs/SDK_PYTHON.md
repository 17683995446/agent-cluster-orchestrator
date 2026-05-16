# Agent Cluster Orchestrator SDK

Python SDK for interacting with the Agent Cluster Orchestrator API.

## Installation

```bash
pip install agent-cluster-sdk
```

## Quick Start

```python
from agent_cluster_sdk import Client

# Initialize client
client = Client(
    base_url="https://api.example.com",
    api_key="your-api-key"
)

# Login
client.auth.login(username="user", password="pass")

# Create an agent
agent = client.agents.create(
    name="my-agent",
    capabilities=["code_generation", "data_analysis"],
    model="gpt-4",
    provider="openai"
)

# Create a task
task = client.tasks.create(
    description="Analyze sales data",
    type="data_analysis",
    priority=1,
    input_data={"data_source": "sales.db"}
)

# Get task result
result = client.tasks.get_result(task.id)
print(result)
```

## Authentication

### API Key Authentication

```python
from agent_cluster_sdk import Client

client = Client(api_key="ak_your_api_key_here")
```

### JWT Authentication

```python
from agent_cluster_sdk import Client

client = Client()
client.auth.login(username="user", password="password")

# All subsequent requests will use the JWT token
agents = client.agents.list()
```

## Agent Management

### Create Agent

```python
agent = client.agents.create(
    name="data-analyst",
    capabilities=["data_analysis", "visualization", "sql_queries"],
    model="gpt-4",
    provider="openai",
    max_concurrent_tasks=5,
    metadata={"team": "analytics"}
)
```

### List Agents

```python
# List all agents
agents = client.agents.list()

# List with filters
agents = client.agents.list(
    status="active",
    capabilities=["data_analysis"],
    limit=10,
    offset=0
)
```

### Get Agent

```python
agent = client.agents.get("agent-uuid-here")
```

### Update Agent

```python
agent = client.agents.update(
    "agent-uuid-here",
    max_concurrent_tasks=10,
    status="disabled"
)
```

### Delete Agent

```python
client.agents.delete("agent-uuid-here")
```

## Task Management

### Create Task

```python
task = client.tasks.create(
    description="Generate quarterly sales report",
    type="data_analysis",
    priority=1,
    input_data={
        "quarter": "Q4",
        "year": 2024,
        "region": "APAC"
    },
    required_capabilities=["data_analysis", "visualization"]
)
```

### Get Task

```python
task = client.tasks.get("task-uuid-here")
print(f"Status: {task.status}")
print(f"Progress: {task.progress}%")
```

### List Tasks

```python
tasks = client.tasks.list(
    status="completed",
    limit=50
)
```

### Get Task Result

```python
result = client.tasks.get_result("task-uuid-here")
if result.status == "completed":
    print(f"Output: {result.output}")
    print(f"Metrics: {result.metrics}")
```

## Cluster Execution

### Execute Cluster Task

```python
cluster_task = client.cluster.execute(
    description="Comprehensive market analysis",
    subtasks=[
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
    ],
    execution_strategy="parallel"
)

print(f"Cluster Task ID: {cluster_task.id}")
print(f"Subtasks: {len(cluster_task.subtasks)}")
```

## WebSocket Real-time Updates

```python
import asyncio
from agent_cluster_sdk import WebSocketClient

async def main():
    client = WebSocketClient("wss://api.example.com/ws")
    
    # Connect
    await client.connect()
    
    # Subscribe to updates
    await client.subscribe(["tasks", "agents"])
    
    # Handle messages
    async def on_message(message):
        print(f"Received: {message.type}")
        if message.type == "task_completed":
            print(f"Task {message.data.task_id} completed!")
    
    client.on_message(on_message)
    
    # Keep connection alive
    await asyncio.sleep(3600)

asyncio.run(main())
```

## Error Handling

```python
from agent_cluster_sdk import (
    Client,
    AuthenticationError,
    RateLimitError,
    APIError
)

try:
    client = Client()
    client.auth.login(username="user", password="pass")
    
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
    
except RateLimitError as e:
    print(f"Rate limited. Retry after: {e.retry_after}s")
    
except APIError as e:
    print(f"API error: {e.code} - {e.message}")
```

## Configuration Options

```python
from agent_cluster_sdk import Client, Config

config = Config(
    base_url="https://api.example.com",
    timeout=30,
    max_retries=3,
    retry_delay=1,
    rate_limit_per_second=10
)

client = Client(config=config)
```

## Advanced Usage

### Async Support

```python
import asyncio
from agent_cluster_sdk import AsyncClient

async def main():
    async with AsyncClient() as client:
        await client.auth.login(username="user", password="pass")
        
        # Concurrent requests
        agents, tasks = await asyncio.gather(
            client.agents.list(),
            client.tasks.list()
        )
        
        print(f"Found {len(agents)} agents and {len(tasks)} tasks")

asyncio.run(main())
```

### Batch Operations

```python
# Create multiple agents
agents = client.agents.batch_create([
    {"name": "agent-1", "capabilities": ["code_generation"]},
    {"name": "agent-2", "capabilities": ["data_analysis"]},
    {"name": "agent-3", "capabilities": ["text_generation"]}
])
```

## Streaming Responses

```python
from agent_cluster_sdk import StreamResponse

# Stream task execution
for chunk in client.tasks.stream("task-id"):
    print(chunk.content, end="", flush=True)
```

## Metrics and Monitoring

```python
# Get cluster statistics
stats = client.cluster.stats()
print(f"Active agents: {stats.active_agents}")
print(f"Queued tasks: {stats.queued_tasks}")
print(f"Success rate: {stats.success_rate}%")
```

## Full Example

```python
from agent_cluster_sdk import Client
import time

def main():
    # Initialize
    client = Client(base_url="https://api.example.com")
    client.auth.login(username="analyst", password="secure123!")
    
    # Create analysis agent
    print("Creating analysis agent...")
    agent = client.agents.create(
        name="sales-analyst",
        capabilities=["data_analysis", "visualization"],
        model="gpt-4"
    )
    
    # Submit analysis task
    print("Submitting analysis task...")
    task = client.tasks.create(
        description="Q4 Sales Analysis",
        type="data_analysis",
        input_data={"quarter": 4, "year": 2024}
    )
    
    # Poll for completion
    print("Processing...")
    while task.status not in ["completed", "failed"]:
        time.sleep(2)
        task = client.tasks.get(task.id)
        print(f"  Status: {task.status} ({task.progress}%)")
    
    # Get results
    if task.status == "completed":
        result = client.tasks.get_result(task.id)
        print(f"\nResults:\n{result.output}")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
```

## License

MIT License - see LICENSE file for details.
