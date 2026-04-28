from celery import Celery

from app.core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "allfind",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=120,
    task_soft_time_limit=90,
    worker_prefetch_multiplier=1,
)
