"""Lightweight Redis-backed job state tracking for batch processing."""

import json
import time
from typing import Any, Dict, List, Optional, Tuple

import redis

from . import settings


class JobStore:
    """Persist job + item state in Redis so workers and API share progress."""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.client = redis.from_url(self.redis_url, decode_responses=True)

    def _key(self, job_id: str) -> str:
        return f"job:{job_id}"

    def create_job(self, job_id: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        job = {
            "job_id": job_id,
            "status": "queued",
            "message": "Queued",
            "items": items,
            "created_at": time.time(),
        }
        self._save(job)
        return job

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        raw = self.client.get(self._key(job_id))
        if raw is None:
            return None
        return json.loads(raw)

    def update_item(self, job_id: str, file_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        job = self.get_job(job_id)
        if not job:
            return None

        updated = False
        for item in job["items"]:
            if item["file_id"] == file_id:
                for key, value in fields.items():
                    if value is not None:
                        item[key] = value
                updated = True
                break

        if not updated:
            return None

        job["status"], job["message"] = self._derive_batch_status(job["items"])
        self._save(job)
        return job

    def update_job(self, job_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        job = self.get_job(job_id)
        if not job:
            return None

        for key, value in fields.items():
            if value is not None:
                job[key] = value

        if "items" in fields:
            job["status"], job["message"] = self._derive_batch_status(job["items"])

        self._save(job)
        return job

    def _derive_batch_status(self, items: List[Dict[str, Any]]) -> Tuple[str, str]:
        if not items:
            return "failed", "No files provided."

        total = len(items)
        completed = sum(1 for i in items if i.get("status") == "completed")
        failed = sum(1 for i in items if i.get("status") == "failed")
        processing = sum(1 for i in items if i.get("status") == "processing")
        queued = sum(1 for i in items if i.get("status") == "queued")

        if completed == total:
            return "completed", f"All files completed ({completed}/{total})."
        if failed > 0 and processing == 0 and queued == 0:
            return "failed", f"{failed} file(s) failed ({completed}/{total} succeeded)."
        if processing > 0:
            return "processing", f"Processing {processing}/{total}. Completed {completed}."
        return "queued", f"Waiting to process {queued}/{total}."

    def _save(self, job: Dict[str, Any]) -> None:
        self.client.set(self._key(job["job_id"]), json.dumps(job))


job_store = JobStore()
