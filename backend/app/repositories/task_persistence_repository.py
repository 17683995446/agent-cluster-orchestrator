from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime
from app.models.task_data_model import Task, TaskStatus

class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, task: Task) -> Task:
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def get_by_id(self, task_id: str) -> Optional[Task]:
        result = await self.session.execute(
            select(Task).where(Task.id == task_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100, status: Optional[TaskStatus] = None) -> List[Task]:
        query = select(Task).order_by(Task.created_at.desc())
        if status:
            query = query.where(Task.status == status)
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_status(self, status: TaskStatus) -> List[Task]:
        result = await self.session.execute(
            select(Task).where(Task.status == status)
        )
        return list(result.scalars().all())

    async def get_by_agent(self, agent_id: str) -> List[Task]:
        result = await self.session.execute(
            select(Task).where(Task.assigned_agent_id == agent_id)
        )
        return list(result.scalars().all())

    async def get_by_parent(self, parent_id: str) -> List[Task]:
        result = await self.session.execute(
            select(Task).where(Task.parent_task_id == parent_id)
        )
        return list(result.scalars().all())

    async def update(self, task: Task) -> Task:
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def update_status(self, task_id: str, status: TaskStatus) -> bool:
        values = {"status": status}
        if status == TaskStatus.RUNNING:
            values["started_at"] = datetime.utcnow()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            values["completed_at"] = datetime.utcnow()
        
        result = await self.session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(**values)
        )
        return result.rowcount > 0

    async def assign_agent(self, task_id: str, agent_id: str) -> bool:
        result = await self.session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(
                assigned_agent_id=agent_id,
                status=TaskStatus.RUNNING,
                started_at=datetime.utcnow()
            )
        )
        return result.rowcount > 0

    async def set_result(self, task_id: str, result: dict) -> bool:
        result = await self.session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(
                result=result,
                status=TaskStatus.COMPLETED,
                completed_at=datetime.utcnow()
            )
        )
        return result.rowcount > 0

    async def set_error(self, task_id: str, error: str) -> bool:
        result = await self.session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(
                error=error,
                status=TaskStatus.FAILED,
                completed_at=datetime.utcnow()
            )
        )
        return result.rowcount > 0

    async def increment_retry(self, task_id: str) -> int:
        result = await self.session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(retry_count=Task.retry_count + 1)
            .returning(Task.retry_count)
        )
        return result.scalar() or 0

    async def delete(self, task_id: str) -> bool:
        result = await self.session.execute(
            delete(Task).where(Task.id == task_id)
        )
        return result.rowcount > 0

    async def count_by_status(self) -> dict:
        result = await self.session.execute(
            select(Task.status, func.count(Task.id))
            .group_by(Task.status)
        )
        return dict(result.all())

    async def count_total(self) -> int:
        result = await self.session.execute(
            select(func.count(Task.id))
        )
        return result.scalar() or 0

    async def count_completed_with_failures(self) -> tuple:
        completed = await self.session.execute(
            select(func.count(Task.id)).where(Task.status == TaskStatus.COMPLETED)
        )
        failed = await self.session.execute(
            select(func.count(Task.id)).where(Task.status == TaskStatus.FAILED)
        )
        return (completed.scalar() or 0, failed.scalar() or 0)

    async def get_avg_response_time(self) -> float:
        result = await self.session.execute(
            select(func.avg(
                func.extract('epoch', Task.completed_at) - func.extract('epoch', Task.started_at)
            )).where(Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED]))
        )
        return result.scalar() or 0.0
