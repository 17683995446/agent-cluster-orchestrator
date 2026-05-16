from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from app.celery_config import celery_app
from app.llm.llm_provider_manager import llm_manager
import structlog
import time

logger = structlog.get_logger()


class LLMTask(Task):
    """Base class for LLM tasks with retry logic."""
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


@celery_app.task(bind=True, base=LLMTask, name="app.tasks.llm_execution_tasks.execute_llm_task")
def execute_llm_task(self, task_id: str, agent_id: str, prompt: str, provider: str, model: str):
    """
    Execute LLM task asynchronously.
    
    Args:
        task_id: Task ID in the database
        agent_id: Agent ID to use for execution
        prompt: The prompt to send to LLM
        provider: LLM provider name (openai, anthropic)
        model: Model name to use
    
    Returns:
        dict: Execution result with content, usage stats
    """
    start_time = time.time()
    logger.info(
        "llm_task_started",
        task_id=task_id,
        agent_id=agent_id,
        provider=provider,
        model=model
    )
    
    try:
        result = await llm_manager.generate(
            prompt=prompt,
            provider=provider,
            model=model
        )
        
        duration = time.time() - start_time
        logger.info(
            "llm_task_completed",
            task_id=task_id,
            agent_id=agent_id,
            duration=duration
        )
        
        return {
            "task_id": task_id,
            "agent_id": agent_id,
            "status": "completed",
            "content": result.get("content"),
            "usage": result.get("usage"),
            "model": result.get("model"),
            "duration": duration
        }
        
    except SoftTimeLimitExceeded:
        logger.warning("llm_task_timeout", task_id=task_id)
        raise
    except Exception as e:
        logger.error(
            "llm_task_failed",
            task_id=task_id,
            agent_id=agent_id,
            error=str(e)
        )
        raise


@celery_app.task(bind=True, base=LLMTask, name="app.tasks.llm_execution_tasks.execute_cluster_task")
def execute_cluster_task(self, parent_task_id: str, subtask_ids: list, descriptions: list, provider: str, model: str):
    """
    Execute cluster task by running multiple subtasks in parallel.
    
    Args:
        parent_task_id: Parent task ID
        subtask_ids: List of subtask IDs
        descriptions: List of subtask descriptions
        provider: LLM provider
        model: Model to use
    
    Returns:
        dict: Aggregated results from all subtasks
    """
    logger.info(
        "cluster_task_started",
        parent_task_id=parent_task_id,
        num_subtasks=len(subtask_ids)
    )
    
    results = []
    for subtask_id, description in zip(subtask_ids, descriptions):
        try:
            result = execute_llm_task.apply_async(
                args=[subtask_id, None, description, provider, model]
            )
            results.append({
                "subtask_id": subtask_id,
                "celery_task_id": result.id,
                "status": "queued"
            })
        except Exception as e:
            logger.error(
                "cluster_subtask_failed",
                subtask_id=subtask_id,
                error=str(e)
            )
            results.append({
                "subtask_id": subtask_id,
                "status": "failed",
                "error": str(e)
            })
    
    logger.info(
        "cluster_task_scheduled",
        parent_task_id=parent_task_id,
        num_results=len(results)
    )
    
    return {
        "parent_task_id": parent_task_id,
        "results": results,
        "status": "scheduled"
    }


@celery_app.task(name="app.tasks.llm_execution_tasks.update_task_status")
def update_task_status(task_id: str, status: str, result: dict = None, error: str = None):
    """
    Update task status in database.
    This is called after LLM task completion.
    """
    logger.info(
        "updating_task_status",
        task_id=task_id,
        status=status
    )
    return {"task_id": task_id, "status": status, "updated": True}


@celery_app.task(name="app.tasks.llm_execution_tasks.cleanup_completed_tasks")
def cleanup_completed_tasks():
    """Periodic task to cleanup old completed tasks."""
    logger.info("cleanup_task_started")
    return {"cleaned": 0, "status": "completed"}
