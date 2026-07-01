from pydantic import BaseModel

from app.schemas.common import ApiResponse
from app.schemas.job import JobData


class DetectionData(BaseModel):
    id: int
    source_video_path: str
    source_filename: str
    source_sha256: str
    file_size: int
    duration: float | None
    fps: float | None
    frame_count: int | None
    width: int | None
    height: int | None
    model_version_id: int
    settings: dict[str, object]
    timeline_path: str | None
    summary: dict[str, object] | None
    status: str
    job_id: int | None


class DetectionSegmentData(BaseModel):
    id: int
    detection_result_id: int
    segment_index: int
    start_sec: float
    end_sec: float
    padded_start_sec: float
    padded_end_sec: float
    duration_sec: float
    score: float
    max_score: float
    average_score: float
    representative_timestamp_sec: float
    start_frame_index: int | None
    end_frame_index: int | None
    status: str
    metadata: dict[str, object]


class DetectionResponse(ApiResponse[DetectionData]):
    pass


class DetectionListResponse(ApiResponse[list[DetectionData]]):
    pass


class DetectionJobResponse(ApiResponse[JobData]):
    pass


class DetectionTimelineResponse(ApiResponse[dict[str, object]]):
    pass


class DetectionSegmentListResponse(ApiResponse[list[DetectionSegmentData]]):
    pass
