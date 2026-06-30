from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.core.errors import ValidationAppError


@dataclass(frozen=True)
class GpuInfo:
    torch_available: bool
    cuda_available: bool
    cuda_enabled: bool
    device_count: int
    device_name: str | None
    torch_version: str | None
    cuda_version: str | None
    memory_allocated_bytes: int | None
    memory_reserved_bytes: int | None


class GpuService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_info(self) -> GpuInfo:
        try:
            import torch
        except ImportError:
            return GpuInfo(
                torch_available=False,
                cuda_available=False,
                cuda_enabled=self.settings.cuda_enabled,
                device_count=0,
                device_name=None,
                torch_version=None,
                cuda_version=None,
                memory_allocated_bytes=None,
                memory_reserved_bytes=None,
            )

        cuda_available = bool(torch.cuda.is_available())
        device_count = int(torch.cuda.device_count()) if cuda_available else 0
        device_name = torch.cuda.get_device_name(0) if device_count > 0 else None
        memory_allocated = (
            int(torch.cuda.memory_allocated(0)) if device_count > 0 else None
        )
        memory_reserved = int(torch.cuda.memory_reserved(0)) if device_count > 0 else None
        return GpuInfo(
            torch_available=True,
            cuda_available=cuda_available,
            cuda_enabled=self.settings.cuda_enabled,
            device_count=device_count,
            device_name=device_name,
            torch_version=getattr(torch, "__version__", None),
            cuda_version=getattr(torch.version, "cuda", None),
            memory_allocated_bytes=memory_allocated,
            memory_reserved_bytes=memory_reserved,
        )

    def require_cuda_available(self) -> GpuInfo:
        info = self.get_info()
        if not info.torch_available:
            raise ValidationAppError(
                message="PyTorch is not installed.",
                detail=info.__dict__,
                suggested_action="Install PyTorch with CUDA support before feature extraction.",
            )
        if not info.cuda_enabled:
            raise ValidationAppError(
                message="CUDA is disabled in settings.",
                detail=info.__dict__,
                suggested_action="Enable AISD_CUDA_ENABLED for feature extraction.",
            )
        if not info.cuda_available:
            raise ValidationAppError(
                message="CUDA GPU is not available.",
                detail=info.__dict__,
                suggested_action="Check NVIDIA driver, CUDA PyTorch wheel, and GPU availability.",
            )
        return info
