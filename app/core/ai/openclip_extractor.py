from typing import Any

_MODEL_CACHE: dict[tuple[str, str, str], tuple[Any, Any]] = {}

from app.core.ai.feature_extractor import ExtractedFeatures, FeatureExtractor
from app.core.config import Settings
from app.core.errors import ValidationAppError


class OpenCLIPFeatureExtractor(FeatureExtractor):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        try:
            from PIL import Image
            import open_clip
            import torch
        except ImportError as exc:
            raise ValidationAppError(
                message="OpenCLIP, PyTorch, or Pillow is not installed.",
                suggested_action="Install dependencies with setup.bat.",
            ) from exc

        self.Image = Image
        if not torch.cuda.is_available():
            raise ValidationAppError(
                message="CUDA GPU is not available for OpenCLIP feature extraction.",
                suggested_action="Install CUDA-enabled PyTorch and check NVIDIA driver.",
            )

        self.torch = torch
        self.device = torch.device("cuda")
        cache_key = (
            settings.openclip_model_name,
            settings.openclip_pretrained,
            str(self.device),
        )
        if cache_key in _MODEL_CACHE:
            self.model, self.preprocess = _MODEL_CACHE[cache_key]
        else:
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                settings.openclip_model_name,
                pretrained=settings.openclip_pretrained,
                device=self.device,
            )
            _MODEL_CACHE[cache_key] = (self.model, self.preprocess)
        self.model.eval()

    def encode_frames(self, rgb_frames: list[Any]) -> ExtractedFeatures:
        if not rgb_frames:
            raise ValidationAppError(message="No frames were provided for feature extraction.")

        images = [
            self.preprocess(self.Image.fromarray(frame)).unsqueeze(0)
            for frame in rgb_frames
        ]
        batch = self.torch.cat(images, dim=0).to(self.device, non_blocking=True)
        with self.torch.no_grad():
            with self.torch.autocast(device_type="cuda"):
                features = self.model.encode_image(batch)
            features = features / features.norm(dim=-1, keepdim=True)

        if self.settings.openclip_feature_dtype == "float16":
            features = features.to(dtype=self.torch.float16)
        else:
            features = features.to(dtype=self.torch.float32)
        cpu_features = features.detach().cpu().numpy()
        return ExtractedFeatures(
            vectors=cpu_features,
            dtype=str(cpu_features.dtype),
            shape=tuple(cpu_features.shape),
            extractor_metadata=self.metadata(),
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "extractor": "openclip",
            "model_name": self.settings.openclip_model_name,
            "pretrained": self.settings.openclip_pretrained,
            "feature_dtype": self.settings.openclip_feature_dtype,
            "device": "cuda",
        }

    def is_out_of_memory_error(self, exc: RuntimeError) -> bool:
        message = str(exc).lower()
        return "out of memory" in message or "cuda error: out of memory" in message

    def clear_memory_after_oom(self) -> None:
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()

    def release(self) -> None:
        # Models are cached for reuse across jobs; release only transient CUDA cache.
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()
