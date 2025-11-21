"""Celery application shared by API and worker processes."""

from celery import Celery  # Celery app factory

from . import settings  # provides Redis URL

# Single Celery app used by both the FastAPI process (to enqueue) and the worker
celery_app = Celery(
    "skate_vid_cropper",  # app name shown in logs
    broker=settings.REDIS_URL,  # message broker where tasks are queued
    backend=settings.REDIS_URL,  # store task results/progress (also Redis here)
)

# Prefer JSON payloads for compatibility/safety
celery_app.conf.update(
    task_serializer="json",  # how tasks are serialized when sent to broker
    accept_content=["json"],  # only accept JSON from publishers
    result_serializer="json",  # serialize results in JSON too
    timezone="UTC",  # default timezone for tasks/schedules
)

# Load any @celery_app.task definitions in this package (e.g., tasks.py)
celery_app.autodiscover_tasks(["src"])
