import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.unit_of_work import UnitOfWork
from app.models.job import Job, JobLog
from app.repositories.job_repository import JobRepository


class JobCancelledError(RuntimeError):
    def __init__(self, job_id: int) -> None:
        super().__init__(f"Job cancel requested: {job_id}")
        self.job_id = job_id


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

    def update_progress(
        self,
        job_id: int,
        progress: int,
        step: str,
        checkpoint: dict[str, Any] | None = None,
    ) -> None:
        job = self._require_job(job_id)
        with UnitOfWork(self.db):
            job.progress = max(0, min(progress, 100))
            job.current_step = step
            if checkpoint is not None:
                job.checkpoint_json = json.dumps(checkpoint, ensure_ascii=True)

    def request_cancel(self, job_id: int) -> Job:
        job = self._require_job(job_id)
        with UnitOfWork(self.db):
            if job.status in {"queued", "running"}:
                job.status = "cancel_requested"
                job.current_step = "cancel_requested"
        return job

    def raise_if_cancel_requested(self, job_id: int) -> None:
        self.db.expire_all()
        job = self._require_job(job_id)
        if job.status == "cancel_requested":
            raise JobCancelledError(job_id)

    def cancel(self, job_id: int, checkpoint: dict[str, Any] | None = None) -> None:
        job = self._require_job(job_id)
        with UnitOfWork(self.db):
            job.status = "cancelled"
            job.current_step = "cancelled"
            if checkpoint is not None:
                job.checkpoint_json = json.dumps(checkpoint, ensure_ascii=True)
            job.finished_at = datetime.now(timezone.utc)

    def retry(self, job_id: int) -> Job:
        source = self._require_job(job_id)
        params = json.loads(source.params_json or "{}")
        retry_count = int(params.get("retry_count", 0)) + 1
        params["retry_count"] = retry_count
        params["retry_of_job_id"] = source.id
        params["resume_checkpoint"] = json.loads(source.checkpoint_json or "{}")
        return self.create_job(source.type, params)

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
            raise NotFoundError(
                message="Job was not found.",
                detail={"job_id": job_id},
            )
        return job
