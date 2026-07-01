from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job, JobLog
from app.repositories.base import Repository


class JobRepository(Repository[Job]):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def add(self, job: Job) -> Job:
        self.db.add(job)
        return job

    def get(self, job_id: int) -> Job | None:
        return self.db.get(Job, job_id)

    def add_log(self, log: JobLog) -> JobLog:
        self.db.add(log)
        return log

    def list_recent(self, limit: int = 50) -> list[Job]:
        return list(
            self.db.execute(
                select(Job).order_by(Job.created_at.desc()).limit(limit)
            ).scalars()
        )

    def list_active_by_type(self, job_type: str) -> list[Job]:
        return list(
            self.db.execute(
                select(Job)
                .where(
                    Job.type == job_type,
                    Job.status.in_(("queued", "running", "cancel_requested", "retrying")),
                )
                .order_by(Job.created_at.desc())
            ).scalars()
        )
