from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.job import Job
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobData, JobResponse
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> JobResponse:
    job = JobRepository(db).get(job_id)
    return JobResponse(
        data=to_job_data(job),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> JobResponse:
    service = JobService(db)
    service.request_cancel(job_id)
    job = JobRepository(db).get(job_id)
    return JobResponse(
        data=to_job_data(job),
        request_id=getattr(request.state, "request_id", None),
    )


def to_job_data(job: Job | None) -> JobData:
    if job is None:
        from app.core.errors import NotFoundError

        raise NotFoundError(
            message="Job was not found.",
            detail={},
        )
    return JobData(
        id=job.id,
        type=job.type,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        error_code=job.error_code,
        error_message=job.error_message,
    )
