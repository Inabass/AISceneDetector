from fastapi import APIRouter, Depends, Request

from app.core.config import Settings, get_settings
from app.schemas.system import (
    CleanupRequest,
    CleanupResponse,
    CleanupResultData,
    CleanupTargetData,
    StorageAreaData,
    StorageUsageData,
    StorageUsageResponse,
    VideoToolData,
    VideoToolsResponse,
)
from app.services.storage_maintenance_service import StorageMaintenanceService
from app.services.video_tools_service import VideoToolsService

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/video-tools", response_model=VideoToolsResponse)
def video_tools(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> VideoToolsResponse:
    statuses = VideoToolsService(settings).require_available()
    return VideoToolsResponse(
        data=[VideoToolData(**status.__dict__) for status in statuses],
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/storage", response_model=StorageUsageResponse)
def storage_usage(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> StorageUsageResponse:
    usage = StorageMaintenanceService(settings).usage()
    return StorageUsageResponse(
        data=StorageUsageData(
            storage_root=str(usage["storage_root"]),
            total_bytes=int(usage["total_bytes"]),
            areas=[StorageAreaData(**area) for area in usage["areas"]],
        ),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/cleanup", response_model=CleanupResponse)
def cleanup_storage(
    payload: CleanupRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> CleanupResponse:
    result = StorageMaintenanceService(settings).cleanup(
        dry_run=payload.dry_run,
        targets=payload.targets,
        older_than_hours=payload.older_than_hours,
    )
    return CleanupResponse(
        data=CleanupResultData(
            dry_run=bool(result["dry_run"]),
            targets=[CleanupTargetData(**target) for target in result["targets"]],
            deleted_file_count=int(result["deleted_file_count"]),
            deleted_bytes=int(result["deleted_bytes"]),
            skipped_file_count=int(result["skipped_file_count"]),
            errors=list(result["errors"]),
        ),
        request_id=getattr(request.state, "request_id", None),
    )
