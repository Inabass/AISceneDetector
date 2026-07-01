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


class StorageAreaData(BaseModel):
    name: str
    path: str
    file_count: int
    total_bytes: int


class StorageUsageData(BaseModel):
    storage_root: str
    total_bytes: int
    areas: list[StorageAreaData]


class StorageUsageResponse(ApiResponse[StorageUsageData]):
    pass


class CleanupRequest(BaseModel):
    dry_run: bool = True
    targets: list[str] | None = None
    older_than_hours: int = 24


class CleanupTargetData(BaseModel):
    name: str
    file_count: int
    total_bytes: int


class CleanupResultData(BaseModel):
    dry_run: bool
    targets: list[CleanupTargetData]
    deleted_file_count: int
    deleted_bytes: int
    skipped_file_count: int
    errors: list[str]


class CleanupResponse(ApiResponse[CleanupResultData]):
    pass
