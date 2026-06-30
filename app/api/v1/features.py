from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.job import Job
from app.repositories.job_repository import JobRepository
from app.schemas.job import FeatureJobRequest, JobData, JobResponse
from app.services.feature_service import FeatureService

router = APIRouter(prefix="/training", tags=["features"])


@router.post("/videos/{video_id}/features", response_model=JobResponse, status_code=202)
def create_training_feature_job(
    video_id: int,
    payload: FeatureJobRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    job_id = FeatureService(db, settings).create_training_feature_job(
        video_id=video_id,
        frame_interval_sec=payload.frame_interval_sec,
        batch_size=payload.batch_size,
    )
    job = JobRepository(db).get(job_id)
    return JobResponse(
        data=to_job_data(job),
        request_id=getattr(request.state, "request_id", None),
    )


def to_job_data(job: Job | None) -> JobData:
    if job is None:
        raise RuntimeError("Job was not created")
    return JobData(
        id=job.id,
        type=job.type,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        error_code=job.error_code,
        error_message=job.error_message,
    )
