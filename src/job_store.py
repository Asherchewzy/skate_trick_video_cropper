"""Lightweight Redis-backed job state tracking for batch processing."""

import json
import time
from typing import Any

import redis

from . import settings


class JobStore:
    """Persist job + item state in Redis so workers and API share progress."""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or settings.REDIS_URL  # allow override for tests
        self.client = redis.from_url(self.redis_url, decode_responses=True)  # string responses

    def _key(self, job_id: str) -> str:
        # Namespaced key per batch job
        return f"job:{job_id}"

    def create_job(self, job_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        # Initial payload we persist in Redis
        job = {
            "job_id": job_id,
            "status": "queued",
            "message": "Queued",
            "items": items,
            "created_at": time.time(),
        }
        self._save(job)
        return job

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        raw = self.client.get(self._key(job_id))  # fetch JSON string or None
        if raw is None:
            return None
        return json.loads(raw)  # decode back into a Python dict

    def update_item(self, job_id: str, file_id: str, **fields: Any) -> dict[str, Any] | None:
        job = self.get_job(job_id)  # load the current job snapshot
        if not job:
            return None  # unknown job

        updated = False
        for item in job["items"]:  # find the matching file entry
            if item["file_id"] == file_id:
                for key, value in fields.items():  # set provided fields
                    if value is not None:
                        item[key] = value
                updated = True
                break

        if not updated:
            return None

        job["status"], job["message"] = self._derive_batch_status(job["items"])  # recalc batch status
        self._save(job)  # write back to Redis
        return job

    def update_job(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        job = self.get_job(job_id)  # fetch existing job
        if not job:
            return None

        for key, value in fields.items():
            if value is not None:
                job[key] = value

        if "items" in fields:
            job["status"], job["message"] = self._derive_batch_status(job["items"])

        self._save(job)  # persist the modified job
        return job

    def _derive_batch_status(self, items: list[dict[str, Any]]) -> tuple[str, str]:
        if not items:
            return "failed", "No files provided."

        # Aggregate item states to describe the overall batch
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

    def _save(self, job: dict[str, Any]) -> None:
        # Store the job as a JSON string at a deterministic key
        self.client.set(self._key(job["job_id"]), json.dumps(job))


job_store = JobStore()
