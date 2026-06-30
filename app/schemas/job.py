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


class FeatureJobRequest(BaseModel):
    frame_interval_sec: float | None = None
    batch_size: int | None = None
