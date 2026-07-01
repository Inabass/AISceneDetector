from pydantic import BaseModel

from app.schemas.common import ApiResponse


class JobData(BaseModel):
    id: int
    type: str
    status: str
    progress: int
    current_step: str | None
    error_code: str | None
    error_message: str | None


class JobResponse(ApiResponse[JobData]):
    pass


class JobListResponse(ApiResponse[list[JobData]]):
    pass


class JobLogData(BaseModel):
    id: int
    job_id: int
    level: str
    step: str | None
    message: str
    details: dict[str, object] | None
    created_at: str


class JobLogListResponse(ApiResponse[list[JobLogData]]):
    pass


class FeatureJobRequest(BaseModel):
    frame_interval_sec: float | None = None
    batch_size: int | None = None
