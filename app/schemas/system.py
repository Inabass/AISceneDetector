from pydantic import BaseModel

from app.schemas.common import ApiResponse


class VideoToolData(BaseModel):
    name: str
    configured_path: str | None
    resolved_path: str | None
    available: bool
    version: str | None
    error: str | None = None


class VideoToolsResponse(ApiResponse[list[VideoToolData]]):
    pass
