"""Celery application shared by API and worker processes."""

from celery import Celery 

from . import settings  

# Single Celery app used by both the FastAPI process (to enqueue) and the worker
celery_app = Celery(
    "skate_vid_cropper",  # app name shown in logs
    broker=settings.REDIS_URL,  # message broker where tasks are queued
    backend=settings.REDIS_URL,  # store task results/progress (also Redis here)
)

celery_app.conf.update(
    task_serializer="json",  
    accept_content=["json"],  
    result_serializer="json", 
    timezone="UTC",  # default timezone for tasks/schedules
)

# Load any @celery_app.task definitions in src
celery_app.autodiscover_tasks(["src"])
