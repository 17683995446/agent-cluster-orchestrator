from celery import Celery
from celery.signals import worker_ready, worker_shutdowning
import structlog

logger = structlog.get_logger()

def create_celery_app():
    """Create and configure Celery application."""
    from app.application_configuration import settings
    
    celery_app = Celery(
        "agent_cluster_tasks",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=["app.tasks.llm_execution_tasks"]
    )
    
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=300,
        task_soft_time_limit=270,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=100,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        result_expires=3600,
        task_routes={
            "app.tasks.llm_execution_tasks.execute_llm_task": {"queue": "llm_tasks"},
            "app.tasks.llm_execution_tasks.execute_cluster_task": {"queue": "cluster_tasks"},
        },
        task_default_queue="default",
        task_default_exchange="agent_cluster",
        task_default_routing_key="default",
    )
    
    @worker_ready.connect
    def on_worker_ready(**kwargs):
        logger.info("celery_worker_ready")
    
    @worker_shutdowning.connect
    def on_worker_shutdown(**kwargs):
        logger.info("celery_worker_shutdown")
    
    return celery_app

celery_app = create_celery_app()
