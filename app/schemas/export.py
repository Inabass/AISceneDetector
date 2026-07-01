from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse
from app.schemas.job import JobData


class ExportRequest(BaseModel):
    detection_id: int
    segment_ids: list[int] | None = None
    mode: str = Field(default="copy", pattern="^(copy|reencode)$")


class ExportData(BaseModel):
    id: int
    detection_result_id: int
    segment_id: int | None
    mode: str
    status: str
    output_path: str | None
    output_url: str | None
    thumbnail_path: str | None
    thumbnail_url: str | None
    preview_path: str | None
    preview_url: str | None
    ffmpeg_args: list[str] | None
    error_message: str | None
    asset_error_message: str | None
    job_id: int | None


class ExportJobResponse(ApiResponse[JobData]):
    pass


class ExportResponse(ApiResponse[ExportData]):
    pass


class ExportListResponse(ApiResponse[list[ExportData]]):
    pass
