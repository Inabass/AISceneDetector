import json

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.export import Export
from app.models.job import Job
from app.repositories.job_repository import JobRepository
from app.schemas.export import (
    ExportData,
    ExportJobResponse,
    ExportListResponse,
    ExportRequest,
    ExportResponse,
)
from app.schemas.job import JobData
from app.services.export_service import ExportService, run_export_job

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("", response_model=ExportJobResponse, status_code=202)
def create_export(
    payload: ExportRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ExportJobResponse:
    service = ExportService(db, settings)
    job_id = service.create_export_job(
        detection_id=payload.detection_id,
        segment_ids=payload.segment_ids,
        mode=payload.mode,
    )
    job = JobRepository(db).get(job_id)
    if job and job.status == "queued":
        background_tasks.add_task(run_export_job, job_id)
    return ExportJobResponse(
        data=to_job_data(job),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("", response_model=ExportListResponse)
def list_exports(
    request: Request,
    limit: int = 50,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ExportListResponse:
    exports = ExportService(db, settings).list_exports(limit)
    return ExportListResponse(
        data=[to_export_data(export) for export in exports],
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/{export_id}", response_model=ExportResponse)
def get_export(
    export_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ExportResponse:
    export = ExportService(db, settings).get_export(export_id)
    return ExportResponse(
        data=to_export_data(export),
        request_id=getattr(request.state, "request_id", None),
    )


def to_export_data(export: Export) -> ExportData:
    return ExportData(
        id=export.id,
        detection_result_id=export.detection_result_id,
        segment_id=export.segment_id,
        mode=export.mode,
        status=export.status,
        output_path=export.output_path,
        output_url=to_media_url(export.output_path),
        thumbnail_path=export.thumbnail_path,
        thumbnail_url=to_media_url(export.thumbnail_path),
        preview_path=export.preview_path,
        preview_url=to_media_url(export.preview_path),
        ffmpeg_args=json.loads(export.ffmpeg_args_json) if export.ffmpeg_args_json else None,
        error_message=export.error_message,
        asset_error_message=export.asset_error_message,
        job_id=export.job_id,
    )


def to_media_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"/media/{path}"


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
