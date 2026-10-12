import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.celery.tasks"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    imports=["src.celery.tasks"],
)

celery.autodiscover_tasks(["src.celery"])

# Explicitly import tasks so worker and callers always have them registered
import src.celery.tasks  # noqa: E402, F401