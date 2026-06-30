from pydantic import BaseModel

from app.schemas.common import ApiResponse


class GpuInfoData(BaseModel):
    torch_available: bool
    cuda_available: bool
    cuda_enabled: bool
    device_count: int
    device_name: str | None
    torch_version: str | None
    cuda_version: str | None
    memory_allocated_bytes: int | None
    memory_reserved_bytes: int | None


class GpuInfoResponse(ApiResponse[GpuInfoData]):
    pass
