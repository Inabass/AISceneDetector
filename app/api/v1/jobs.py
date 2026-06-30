from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.job import Job, JobLog
from app.schemas.job import (
    JobData,
    JobListResponse,
    JobLogData,
    JobLogListResponse,
    JobResponse,
)
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
def list_jobs(
    request: Request,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> JobListResponse:
    jobs = JobService(db).list_recent(limit)
    return JobListResponse(
        data=[to_job_data(job) for job in jobs],
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> JobResponse:
    job = JobService(db).request_cancel(job_id)
    return JobResponse(data=to_job_data(job), request_id=getattr(request.state, "request_id", None))


@router.post("/{job_id}/retry", response_model=JobResponse, status_code=202)
def retry_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> JobResponse:
    job = JobService(db).retry(job_id)
    return JobResponse(data=to_job_data(job), request_id=getattr(request.state, "request_id", None))


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> JobResponse:
    job = JobService(db)._require_job(job_id)
    return JobResponse(data=to_job_data(job), request_id=getattr(request.state, "request_id", None))


@router.get("/{job_id}/logs", response_model=JobLogListResponse)
def list_job_logs(
    job_id: int,
    request: Request,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> JobLogListResponse:
    logs = JobService(db).list_logs(job_id, limit)
    return JobLogListResponse(
        data=[to_job_log_data(log) for log in logs],
        request_id=getattr(request.state, "request_id", None),
    )


def to_job_data(job: Job | None) -> JobData:
    if job is None:
        raise RuntimeError("Job was not found")
    return JobData(
        id=job.id,
        type=job.type,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        error_code=job.error_code,
        error_message=job.error_message,
    )


def to_job_log_data(log: JobLog) -> JobLogData:
    return JobLogData(
        id=log.id,
        job_id=log.job_id,
        level=log.level,
        step=log.step,
        message=log.message,
        details_json=log.details_json,
        created_at=log.created_at.isoformat(),
    )
