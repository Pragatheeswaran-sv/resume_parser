from celery import Celery
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery.autodiscover_tasks(["src.services.background_task"])