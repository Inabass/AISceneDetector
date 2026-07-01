import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.detection import DetectionResult
from app.models.job import Job
from app.repositories.job_repository import JobRepository
from app.schemas.detection import (
    DetectionData,
    DetectionJobResponse,
    DetectionListResponse,
    DetectionResponse,
    DetectionSegmentData,
    DetectionSegmentListResponse,
    DetectionTimelineResponse,
)
from app.schemas.job import JobData
from app.services.detection_service import DetectionService, run_detection_job

router = APIRouter(prefix="/detections", tags=["detections"])


@router.post("", response_model=DetectionJobResponse, status_code=202)
async def create_detection(
    background_tasks: BackgroundTasks,
    request: Request,
    model_id: int | None = Form(default=None),
    model_version_id: int | None = Form(default=None),
    frame_interval_sec: float | None = Form(default=None),
    batch_size: int | None = Form(default=None),
    threshold: float | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DetectionJobResponse:
    service = DetectionService(db, settings)
    job_id = await service.create_detection_job(
        upload=file,
        model_id=model_id,
        model_version_id=model_version_id,
        frame_interval_sec=frame_interval_sec,
        batch_size=batch_size,
        threshold=threshold,
    )
    job = JobRepository(db).get(job_id)
    if job and job.status == "queued":
        background_tasks.add_task(run_detection_job, job_id)
    return DetectionJobResponse(
        data=to_job_data(job),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("", response_model=DetectionListResponse)
def list_detections(
    request: Request,
    limit: int = 50,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DetectionListResponse:
    detections = DetectionService(db, settings).list_detections(limit)
    return DetectionListResponse(
        data=[to_detection_data(detection) for detection in detections],
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/{detection_id}", response_model=DetectionResponse)
def get_detection(
    detection_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DetectionResponse:
    detection = DetectionService(db, settings).get_detection(detection_id)
    return DetectionResponse(
        data=to_detection_data(detection),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/{detection_id}/timeline", response_model=DetectionTimelineResponse)
def get_detection_timeline(
    detection_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DetectionTimelineResponse:
    timeline = DetectionService(db, settings).read_timeline(detection_id)
    return DetectionTimelineResponse(
        data=timeline,
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/{detection_id}/segments", response_model=DetectionSegmentListResponse)
def get_detection_segments(
    detection_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DetectionSegmentListResponse:
    segments = DetectionService(db, settings).list_segments(detection_id)
    return DetectionSegmentListResponse(
        data=[
            DetectionSegmentData(
                id=segment.id,
                detection_result_id=segment.detection_result_id,
                segment_index=segment.segment_index,
                start_sec=segment.start_sec,
                end_sec=segment.end_sec,
                padded_start_sec=segment.padded_start_sec,
                padded_end_sec=segment.padded_end_sec,
                duration_sec=segment.duration_sec,
                score=segment.score,
                max_score=segment.max_score,
                average_score=segment.average_score,
                representative_timestamp_sec=segment.representative_timestamp_sec,
                start_frame_index=segment.start_frame_index,
                end_frame_index=segment.end_frame_index,
                status=segment.status,
                metadata=json.loads(segment.metadata_json),
            )
            for segment in segments
        ],
        request_id=getattr(request.state, "request_id", None),
    )


def to_detection_data(detection: DetectionResult) -> DetectionData:
    return DetectionData(
        id=detection.id,
        source_video_path=detection.source_video_path,
        source_filename=detection.source_filename,
        source_sha256=detection.source_sha256,
        file_size=detection.file_size,
        duration=detection.duration,
        fps=detection.fps,
        frame_count=detection.frame_count,
        width=detection.width,
        height=detection.height,
        model_version_id=detection.model_version_id,
        settings=json.loads(detection.settings_json),
        timeline_path=detection.timeline_path,
        summary=json.loads(detection.summary_json) if detection.summary_json else None,
        status=detection.status,
        job_id=detection.job_id,
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
