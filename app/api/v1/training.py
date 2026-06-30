from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.training_video import TrainingVideo
from app.schemas.video import (
    TrainingVideoData,
    TrainingVideoListResponse,
    TrainingVideoResponse,
)
from app.services.video_service import VideoService

router = APIRouter(prefix="/training", tags=["training"])


@router.post("/videos", response_model=TrainingVideoResponse, status_code=201)
async def upload_training_video(
    request: Request,
    label_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TrainingVideoResponse:
    video = await VideoService(db, settings).register_training_video(file, label_type)
    return TrainingVideoResponse(
        data=to_training_video_data(video),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/videos", response_model=TrainingVideoListResponse)
def list_training_videos(
    request: Request,
    limit: int = 50,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TrainingVideoListResponse:
    videos = VideoService(db, settings).list_training_videos(limit)
    return TrainingVideoListResponse(
        data=[to_training_video_data(video) for video in videos],
        request_id=getattr(request.state, "request_id", None),
    )


def to_training_video_data(video: TrainingVideo) -> TrainingVideoData:
    return TrainingVideoData(
        id=video.id,
        label_type=video.label_type,
        original_filename=video.original_filename,
        stored_filename=video.stored_filename,
        path=video.path,
        sha256=video.sha256,
        file_size=video.file_size,
        extension=video.extension,
        duration=video.duration,
        fps=video.fps,
        frame_count=video.frame_count,
        width=video.width,
        height=video.height,
        codec=video.codec,
        pixel_format=video.pixel_format,
        bitrate=video.bitrate,
        rotation=video.rotation,
        stream_count=video.stream_count,
        has_audio=video.has_audio,
        validation_status=video.validation_status,
        processing_status=video.processing_status,
        validation_error=video.validation_error,
        duplicated=bool(getattr(video, "_duplicated_response", False)),
        duplicate_of_video_id=getattr(
            video,
            "_duplicate_source_video_id",
            video.duplicate_of_video_id,
        ),
    )
