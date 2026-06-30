import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.unit_of_work import UnitOfWork
from app.models.job import Job, JobLog
from app.repositories.job_repository import JobRepository


class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = JobRepository(db)

    def create_job(self, job_type: str, params: dict[str, Any]) -> Job:
        job = Job(
            type=job_type,
            status="queued",
            progress=0,
            current_step="queued",
            params_json=json.dumps(params, ensure_ascii=True),
        )
        with UnitOfWork(self.db):
            self.repository.add(job)
        self.db.refresh(job)
        return job

    def start(self, job_id: int, step: str) -> Job:
        job = self._require_job(job_id)
        with UnitOfWork(self.db):
            job.status = "running"
            job.current_step = step
            job.started_at = datetime.now(timezone.utc)
        return job

    def update_progress(self, job_id: int, progress: int, step: str) -> None:
        job = self._require_job(job_id)
        with UnitOfWork(self.db):
            job.progress = max(0, min(progress, 100))
            job.current_step = step

    def succeed(self, job_id: int, checkpoint: dict[str, Any] | None = None) -> None:
        job = self._require_job(job_id)
        with UnitOfWork(self.db):
            job.status = "succeeded"
            job.progress = 100
            job.current_step = "succeeded"
            job.checkpoint_json = json.dumps(checkpoint or {}, ensure_ascii=True)
            job.finished_at = datetime.now(timezone.utc)

    def fail(self, job_id: int, error_code: str, message: str) -> None:
        job = self._require_job(job_id)
        with UnitOfWork(self.db):
            job.status = "failed"
            job.error_code = error_code
            job.error_message = message
            job.current_step = "failed"
            job.finished_at = datetime.now(timezone.utc)

    def log(
        self,
        job_id: int,
        level: str,
        step: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        log = JobLog(
            job_id=job_id,
            level=level,
            step=step,
            message=message,
            details_json=json.dumps(details, ensure_ascii=True) if details else None,
            created_at=datetime.now(timezone.utc),
        )
        with UnitOfWork(self.db):
            self.repository.add_log(log)

    def _require_job(self, job_id: int) -> Job:
        job = self.repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        return job
