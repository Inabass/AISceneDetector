import json

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ValidationAppError
from app.db.session import get_db
from app.models.job import Job, JobLog
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobData, JobListResponse, JobLogData, JobLogListResponse, JobResponse
from app.services.detection_service import run_detection_job
from app.services.export_service import ExportService, run_export_job
from app.services.feature_service import FeatureService, run_training_feature_job
from app.services.job_service import JobService
from app.services.model_service import ModelService, run_model_training_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
def list_jobs(
    request: Request,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> JobListResponse:
    jobs = JobRepository(db).list_recent(limit=limit)
    return JobListResponse(
        data=[to_job_data(job) for job in jobs],
        request_id=getattr(request.state, "request_id", None),
    )


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


@router.get("/{job_id}/logs", response_model=JobLogListResponse)
def get_job_logs(
    job_id: int,
    request: Request,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> JobLogListResponse:
    repository = JobRepository(db)
    to_job_data(repository.get(job_id))
    logs = repository.list_logs(job_id, limit=limit)
    return JobLogListResponse(
        data=[to_job_log_data(log) for log in logs],
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{job_id}/retry", response_model=JobResponse, status_code=202)
def retry_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    repository = JobRepository(db)
    original = repository.get(job_id)
    to_job_data(original)
    if original.status not in {"failed", "cancelled"}:
        raise ValidationAppError(
            message="Only failed or cancelled jobs can be retried.",
            detail={"job_id": job_id, "status": original.status},
            suggested_action="Wait for the active job to finish or start a new operation.",
        )
    params = _job_params(original)
    new_job_id = _create_retry_job(original.type, params, db, settings)
    new_job = repository.get(new_job_id)
    if new_job and new_job.status == "queued":
        _schedule_retry_job(new_job.type, new_job.id, background_tasks)
    return JobResponse(
        data=to_job_data(new_job),
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


def _job_params(job: Job) -> dict[str, object]:
    try:
        return json.loads(job.params_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValidationAppError(
            message="Job parameters are not readable.",
            detail={"job_id": job.id},
            suggested_action="Start the operation again from the original screen.",
        ) from exc


def _create_retry_job(
    job_type: str,
    params: dict[str, object],
    db: Session,
    settings: Settings,
) -> int:
    if job_type == "training_feature_extraction":
        return FeatureService(db, settings).create_training_feature_job(
            video_id=int(params["video_id"]),
            frame_interval_sec=float(params["frame_interval_sec"])
            if params.get("frame_interval_sec") is not None
            else None,
            batch_size=int(params["batch_size"]) if params.get("batch_size") is not None else None,
        )
    if job_type == "model_training":
        return ModelService(db, settings).create_training_job(
            model_id=int(params["model_id"]),
            parent_version_id=(
                int(params["parent_version_id"])
                if params.get("parent_version_id") is not None
                else None
            ),
            threshold=float(params["threshold"]) if params.get("threshold") is not None else None,
            feature_ids=[int(value) for value in params["feature_ids"]]
            if params.get("feature_ids") is not None
            else None,
            include_feedback=bool(params.get("include_feedback")),
            feedback_ids=[int(value) for value in params["feedback_ids"]]
            if params.get("feedback_ids") is not None
            else None,
        )
    if job_type == "detection":
        return JobService(db).create_job(
            "detection",
            {
                "detection_id": int(params["detection_id"]),
                "model_version_id": int(params["model_version_id"]),
                "frame_interval_sec": float(params["frame_interval_sec"]),
                "batch_size": int(params["batch_size"]),
                "threshold": params.get("threshold"),
            },
        ).id
    if job_type == "export":
        return ExportService(db, settings).create_export_job(
            detection_id=int(params["detection_id"]),
            segment_ids=[int(value) for value in params["segment_ids"]]
            if params.get("segment_ids") is not None
            else None,
            mode=str(params.get("mode") or "copy"),
        )
    raise ValidationAppError(
        message="This job type cannot be retried.",
        detail={"job_type": job_type},
        suggested_action="Start the operation again from the original screen.",
    )


def _schedule_retry_job(
    job_type: str,
    job_id: int,
    background_tasks: BackgroundTasks,
) -> None:
    if job_type == "training_feature_extraction":
        background_tasks.add_task(run_training_feature_job, job_id)
    elif job_type == "model_training":
        background_tasks.add_task(run_model_training_job, job_id)
    elif job_type == "detection":
        background_tasks.add_task(run_detection_job, job_id)
    elif job_type == "export":
        background_tasks.add_task(run_export_job, job_id)


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


def to_job_log_data(log: JobLog) -> JobLogData:
    details = None
    if log.details_json:
        try:
            details = json.loads(log.details_json)
        except json.JSONDecodeError:
            details = {"raw": log.details_json}
    return JobLogData(
        id=log.id,
        job_id=log.job_id,
        level=log.level,
        step=log.step,
        message=log.message,
        details=details,
        created_at=log.created_at.isoformat(),
    )
