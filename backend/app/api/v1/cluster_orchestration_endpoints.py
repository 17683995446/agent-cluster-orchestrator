from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_connection_manager import get_db
from app.services.task_dispatch_and_execution_service import TaskService
from app.schemas.task_api_schemas import ClusterExecuteRequest, ClusterExecuteResponse, TaskDecomposeRequest

router = APIRouter(prefix="/cluster", tags=["Cluster"])

@router.post("/execute", response_model=ClusterExecuteResponse)
async def execute_cluster_task(
    data: ClusterExecuteRequest,
    db: AsyncSession = Depends(get_db)
):
    service = TaskService(db)
    result = await service.execute_cluster_task(data)
    return ClusterExecuteResponse(**result)

@router.get("/stats")
async def get_cluster_stats(db: AsyncSession = Depends(get_db)):
    service = TaskService(db)
    stats = await service.get_cluster_stats()
    return stats.to_dict()
