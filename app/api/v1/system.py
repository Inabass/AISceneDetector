from fastapi import APIRouter, Depends, Request

from app.core.config import Settings, get_settings
from app.schemas.system import VideoToolData, VideoToolsResponse
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
