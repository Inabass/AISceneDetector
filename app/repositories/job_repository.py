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

    def get_next_queued(self, job_types: set[str]) -> Job | None:
        return self.db.execute(
            select(Job)
            .where(Job.status == "queued", Job.type.in_(job_types))
            .order_by(Job.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()

    def list_by_status(self, statuses: set[str], limit: int = 100) -> list[Job]:
        return list(
            self.db.execute(
                select(Job)
                .where(Job.status.in_(statuses))
                .order_by(Job.created_at.asc())
                .limit(limit)
            ).scalars()
        )

    def list_logs(self, job_id: int, limit: int = 200) -> list[JobLog]:
        return list(
            self.db.execute(
                select(JobLog)
                .where(JobLog.job_id == job_id)
                .order_by(JobLog.created_at.asc())
                .limit(limit)
            ).scalars()
        )
