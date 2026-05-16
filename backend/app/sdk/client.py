"""
Phase 3: API文档与开发者体验
Developer SDK and API Client
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class APIConfig:
    """API client configuration."""
    base_url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    timeout: float = 60.0
    max_retries: int = 3
    verify_ssl: bool = True


class AgentClusterClient:
    """
    Python SDK for Agent Cluster Orchestrator.
    
    Features:
    - Async/await support
    - Automatic retry
    - Type hints
    - Context managers
    
    Usage:
        async with AgentClusterClient() as client:
            agents = await client.list_agents()
    """
    
    def __init__(self, config: Optional[APIConfig] = None):
        self.config = config or APIConfig()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def connect(self):
        """Establish connection to API server."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=httpx.Timeout(self.config.timeout),
            verify=self.config.verify_ssl,
            headers={
                "X-API-Key": self.config.api_key or "",
                "Content-Type": "application/json"
            }
        )
        logger.info("client_connected", base_url=self.config.base_url)
    
    async def close(self):
        """Close client connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("client_closed")
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with retry."""
        if not self._client:
            await self.connect()
        
        url = f"{self.config.base_url}{endpoint}"
        
        for attempt in range(self.config.max_retries):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    **kwargs
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    raise
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)


class AgentClient(AgentClusterClient):
    """Client for Agent management endpoints."""
    
    async def create_agent(
        self,
        name: str,
        provider: str = "siliconflow",
        model: str = "Qwen/Qwen2.5-7B-Instruct",
        capabilities: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new agent."""
        data = {
            "name": name,
            "provider": provider,
            "model": model,
            "capabilities": capabilities or []
        }
        return await self._request("POST", "/api/v1/agents", json=data)
    
    async def list_agents(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all agents with pagination."""
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        return await self._request("GET", "/api/v1/agents", params=params)
    
    async def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """Get agent by ID."""
        return await self._request("GET", f"/api/v1/agents/{agent_id}")
    
    async def update_agent(
        self,
        agent_id: str,
        **updates
    ) -> Dict[str, Any]:
        """Update agent."""
        return await self._request(
            "PATCH",
            f"/api/v1/agents/{agent_id}",
            json=updates
        )
    
    async def delete_agent(self, agent_id: str) -> None:
        """Delete agent."""
        await self._request("DELETE", f"/api/v1/agents/{agent_id}")
    
    async def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get agent statistics."""
        return await self._request("GET", f"/api/v1/agents/{agent_id}/stats")


class TaskClient(AgentClusterClient):
    """Client for Task management endpoints."""
    
    async def create_task(
        self,
        description: str,
        priority: int = 1,
        task_type: str = "single"
    ) -> Dict[str, Any]:
        """Create a new task."""
        data = {
            "description": description,
            "priority": priority,
            "type": task_type
        }
        return await self._request("POST", "/api/v1/tasks", json=data)
    
    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all tasks with pagination."""
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        return await self._request("GET", "/api/v1/tasks", params=params)
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get task by ID."""
        return await self._request("GET", f"/api/v1/tasks/{task_id}")
    
    async def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """Get task result."""
        return await self._request("GET", f"/api/v1/tasks/{task_id}/result")
    
    async def cancel_task(self, task_id: str) -> None:
        """Cancel a task."""
        await self._request("DELETE", f"/api/v1/tasks/{task_id}")
    
    async def execute_cluster_task(
        self,
        description: str,
        num_agents: int = 3
    ) -> Dict[str, Any]:
        """Execute a cluster task."""
        data = {
            "description": description,
            "num_agents": num_agents
        }
        return await self._request("POST", "/api/v1/cluster/execute", json=data)


class MonitoringClient(AgentClusterClient):
    """Client for monitoring endpoints."""
    
    async def get_cluster_stats(self) -> Dict[str, Any]:
        """Get cluster statistics."""
        return await self._request("GET", "/api/v1/cluster/stats")
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get system health status."""
        return await self._request("GET", "/health")
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics."""
        return await self._request("GET", "/metrics")


class LLMClient(AgentClusterClient):
    """Client for LLM management endpoints."""
    
    async def list_providers(self) -> List[str]:
        """List available LLM providers."""
        return await self._request("GET", "/api/v1/llm/providers")
    
    async def list_models(self, provider: str) -> List[Dict[str, Any]]:
        """List models for a provider."""
        return await self._request("GET", f"/api/v1/llm/providers/{provider}/models")
    
    async def test_connection(self, provider: str) -> Dict[str, Any]:
        """Test LLM provider connection."""
        return await self._request("POST", f"/api/v1/llm/providers/{provider}/test")


class AgentClusterOrchestrator:
    """
    Main orchestrator client combining all sub-clients.
    
    Usage:
        async with AgentClusterOrchestrator() as orchestrator:
            # Manage agents
            agent = await orchestrator.agents.create_agent("My Agent")
            
            # Manage tasks
            task = await orchestrator.tasks.create_task("Do something")
            
            # Monitor
            stats = await orchestrator.monitoring.get_cluster_stats()
    """
    
    def __init__(self, config: Optional[APIConfig] = None):
        self.config = config or APIConfig()
        self.agents = AgentClient(config)
        self.tasks = TaskClient(config)
        self.monitoring = MonitoringClient(config)
        self.llm = LLMClient(config)
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.agents.connect()
        self.tasks._client = self.agents._client
        self.monitoring._client = self.agents._client
        self.llm._client = self.agents._client
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.agents.close()


async def example_usage():
    """Example usage of the SDK."""
    config = APIConfig(
        base_url="http://localhost:8000",
        api_key="your-api-key"
    )
    
    async with AgentClusterOrchestrator(config) as orchestrator:
        agent = await orchestrator.agents.create_agent(
            name="My First Agent",
            provider="siliconflow",
            model="Qwen/Qwen2.5-7B-Instruct"
        )
        print(f"Created agent: {agent['id']}")
        
        task = await orchestrator.tasks.create_task(
            description="Analyze this data",
            priority=1
        )
        print(f"Created task: {task['id']}")
        
        stats = await orchestrator.monitoring.get_cluster_stats()
        print(f"Total agents: {stats['total_agents']}")
        print(f"Active agents: {stats['active_agents']}")
