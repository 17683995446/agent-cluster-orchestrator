from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_connection_manager import get_db
from app.services.task_dispatch_and_execution_service import TaskService
from app.schemas.task_api_schemas import (
    TaskCreate, TaskResponse, TaskListResponse, TaskResult,
    ClusterExecuteRequest, ClusterExecuteResponse
)
from app.core.enhanced_exception_handler import ResourceNotFoundException
from prometheus_client import Counter, Histogram
import time

router = APIRouter(prefix="/tasks", tags=["Tasks"])

REQUEST_LATENCY = Histogram("task_api_latency_seconds", "Task API latency", ["method"])
REQUEST_COUNT = Counter("task_api_requests_total", "Task API requests", ["method", "endpoint"])

@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    data: TaskCreate,
    db: AsyncSession = Depends(get_db)
):
    start_time = time.time()
    service = TaskService(db)
    task = await service.create(data)
    REQUEST_COUNT.labels(method="POST", endpoint="/tasks").inc()
    REQUEST_LATENCY.labels(method="POST").observe(time.time() - start_time)
    return _task_to_response(task)

@router.get("", response_model=TaskListResponse)
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    start_time = time.time()
    service = TaskService(db)
    status_enum = status if not status else None
    tasks, total = await service.get_all(skip=(page-1)*page_size, limit=page_size, status=status_enum)
    REQUEST_COUNT.labels(method="GET", endpoint="/tasks").inc()
    REQUEST_LATENCY.labels(method="GET").observe(time.time() - start_time)
    return TaskListResponse(
        items=[_task_to_response(t) for t in tasks],
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    service = TaskService(db)
    try:
        task = await service.get(task_id)
        return _task_to_response(task)
    except Exception:
        raise ResourceNotFoundException("Task", task_id)

@router.delete("/{task_id}", status_code=204)
async def cancel_task(task_id: str, db: AsyncSession = Depends(get_db)):
    service = TaskService(db)
    success = await service.cancel(task_id)
    if not success:
        raise ResourceNotFoundException("Task", task_id)

@router.get("/{task_id}/result", response_model=TaskResult)
async def get_task_result(task_id: str, db: AsyncSession = Depends(get_db)):
    service = TaskService(db)
    try:
        task = await service.get(task_id)
        return TaskResult(
            task_id=task.id,
            status=task.status,
            result=task.result,
            error=task.error,
            completed_at=task.completed_at
        )
    except Exception:
        raise ResourceNotFoundException("Task", task_id)

def _task_to_response(task):
    return TaskResponse(
        id=task.id,
        description=task.description,
        type=task.type,
        status=task.status,
        priority=task.priority,
        assigned_agent=task.assigned_agent_id,
        subtasks=task.subtask_ids or [],
        parent_task=task.parent_task_id,
        result=task.result,
        error=task.error,
        retry_count=task.retry_count,
        max_retries=task.max_retries,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at
    )
