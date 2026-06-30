from pydantic import BaseModel

from app.schemas.common import ApiResponse


class TrainingVideoData(BaseModel):
    id: int
    label_type: str
    original_filename: str
    stored_filename: str
    path: str
    sha256: str
    file_size: int
    extension: str
    duration: float | None
    fps: float | None
    frame_count: int | None
    width: int | None
    height: int | None
    codec: str | None
    pixel_format: str | None
    bitrate: int | None
    rotation: int | None
    stream_count: int | None
    has_audio: bool | None
    validation_status: str
    processing_status: str
    validation_error: str | None
    duplicated: bool = False
    duplicate_of_video_id: int | None = None


class TrainingVideoResponse(ApiResponse[TrainingVideoData]):
    pass


class TrainingVideoListResponse(ApiResponse[list[TrainingVideoData]]):
    pass
