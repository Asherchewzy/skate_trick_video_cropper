"""Celery application shared by API and worker processes."""

from celery import Celery

from . import settings

celery_app = Celery(
    "skate_vid_cropper",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Prefer JSON payloads for compatibility/safety
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
)

celery_app.autodiscover_tasks(["app"])
