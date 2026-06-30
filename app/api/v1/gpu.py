from fastapi import APIRouter, Depends, Request

from app.core.config import Settings, get_settings
from app.schemas.gpu import GpuInfoData, GpuInfoResponse
from app.services.gpu_service import GpuService

router = APIRouter(tags=["gpu"])


@router.get("/gpu", response_model=GpuInfoResponse)
def gpu_info(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> GpuInfoResponse:
    info = GpuService(settings).get_info()
    return GpuInfoResponse(
        data=GpuInfoData(**info.__dict__),
        request_id=getattr(request.state, "request_id", None),
    )
