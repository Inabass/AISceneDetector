from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.job import Job
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobData, JobResponse
from app.services.feature_service import run_training_feature_job
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


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
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> JobResponse:
    job = JobService(db).retry(job_id)
    if job.type == "training_feature_extraction":
        background_tasks.add_task(run_training_feature_job, job.id)
    return JobResponse(data=to_job_data(job), request_id=getattr(request.state, "request_id", None))


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> JobResponse:
    job = JobRepository(db).get(job_id)
    return JobResponse(data=to_job_data(job), request_id=getattr(request.state, "request_id", None))


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
