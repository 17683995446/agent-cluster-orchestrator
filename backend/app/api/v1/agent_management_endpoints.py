from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database_connection_manager import get_db
from app.services.agent_lifecycle_management_service import AgentService
from app.schemas.agent_api_schemas import (
    AgentCreate, AgentUpdate, AgentResponse, AgentListResponse,
    AgentStats, CapabilityStats
)
from app.core.enhanced_exception_handler import ResourceNotFoundException
from prometheus_client import Counter, Histogram
import time

router = APIRouter(prefix="/agents", tags=["Agents"])

REQUEST_LATENCY = Histogram("agent_api_latency_seconds", "Agent API latency", ["method"])
REQUEST_COUNT = Counter("agent_api_requests_total", "Agent API requests", ["method", "endpoint"])

@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db)
):
    start_time = time.time()
    service = AgentService(db)
    agent = await service.create(data)
    REQUEST_COUNT.labels(method="POST", endpoint="/agents").inc()
    REQUEST_LATENCY.labels(method="POST").observe(time.time() - start_time)
    return AgentResponse(
        id=agent.id, name=agent.name, capabilities=agent.capabilities,
        status=agent.status, model=agent.model, provider=agent.provider,
        current_task=agent.current_task_id,
        stats=AgentStats(
            total_tasks=agent.total_tasks,
            success_count=agent.success_count,
            failure_count=agent.failure_count,
            total_response_time=agent.total_response_time
        ),
        created_at=agent.created_at,
        last_heartbeat=agent.last_heartbeat
    )

@router.get("", response_model=AgentListResponse)
async def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    start_time = time.time()
    service = AgentService(db)
    agents, total = await service.get_all(skip=(page-1)*page_size, limit=page_size)
    REQUEST_COUNT.labels(method="GET", endpoint="/agents").inc()
    REQUEST_LATENCY.labels(method="GET").observe(time.time() - start_time)
    return AgentListResponse(
        items=[AgentResponse(
            id=a.id, name=a.name, capabilities=a.capabilities,
            status=a.status, model=a.model, provider=a.provider,
            current_task=a.current_task_id,
            stats=AgentStats(
                total_tasks=a.total_tasks,
                success_count=a.success_count,
                failure_count=a.failure_count,
                total_response_time=a.total_response_time
            ),
            created_at=a.created_at,
            last_heartbeat=a.last_heartbeat
        ) for a in agents],
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/stats")
async def get_agent_stats(db: AsyncSession = Depends(get_db)):
    service = AgentService(db)
    return await service.get_stats()

@router.get("/capabilities", response_model=CapabilityStats)
async def get_capability_stats(db: AsyncSession = Depends(get_db)):
    service = AgentService(db)
    return await service.get_capability_stats()

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    service = AgentService(db)
    try:
        agent = await service.get(agent_id)
        return AgentResponse(
            id=agent.id, name=agent.name, capabilities=agent.capabilities,
            status=agent.status, model=agent.model, provider=agent.provider,
            current_task=agent.current_task_id,
            stats=AgentStats(
                total_tasks=agent.total_tasks,
                success_count=agent.success_count,
                failure_count=agent.failure_count,
                total_response_time=agent.total_response_time
            ),
            created_at=agent.created_at,
            last_heartbeat=agent.last_heartbeat
        )
    except Exception:
        raise ResourceNotFoundException("Agent", agent_id)

@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db)
):
    service = AgentService(db)
    try:
        agent = await service.update(agent_id, data)
        return AgentResponse(
            id=agent.id, name=agent.name, capabilities=agent.capabilities,
            status=agent.status, model=agent.model, provider=agent.provider,
            current_task=agent.current_task_id,
            stats=AgentStats(
                total_tasks=agent.total_tasks,
                success_count=agent.success_count,
                failure_count=agent.failure_count,
                total_response_time=agent.total_response_time
            ),
            created_at=agent.created_at,
            last_heartbeat=agent.last_heartbeat
        )
    except Exception:
        raise ResourceNotFoundException("Agent", agent_id)

@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    service = AgentService(db)
    try:
        await service.delete(agent_id)
    except Exception:
        raise ResourceNotFoundException("Agent", agent_id)

@router.post("/{agent_id}/heartbeat")
async def heartbeat(agent_id: str, db: AsyncSession = Depends(get_db)):
    service = AgentService(db)
    success = await service.heartbeat(agent_id)
    if not success:
        raise agent_not_found_error(agent_id)
    return {"status": "ok"}
