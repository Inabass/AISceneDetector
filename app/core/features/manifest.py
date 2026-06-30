import json
from pathlib import Path
from typing import Any, Iterator

import numpy as np
from pydantic import BaseModel, Field

from app.core.errors import ValidationAppError

FEATURE_MANIFEST_SCHEMA_VERSION = 1
FEATURE_MANIFEST_STORAGE = "chunked_npz"


class FeatureChunkManifest(BaseModel):
    path: str
    sha256: str
    size: int
    shape: list[int]
    dtype: str
    first_frame_index: int
    last_frame_index: int
    first_timestamp_sec: float
    last_timestamp_sec: float


class FeatureManifest(BaseModel):
    schema_version: int = FEATURE_MANIFEST_SCHEMA_VERSION
    storage: str = FEATURE_MANIFEST_STORAGE
    status: str = "succeeded"
    chunks: list[FeatureChunkManifest] = Field(default_factory=list)
    frame_count: int
    shape: list[int]
    dtype: str
    cache_key: str
    source_video_id: int
    extractor: dict[str, Any] = Field(default_factory=dict)

    def validate_contract(self) -> None:
        if self.schema_version != FEATURE_MANIFEST_SCHEMA_VERSION:
            raise ValidationAppError(
                message="Unsupported feature manifest schema version.",
                detail={"schema_version": self.schema_version},
            )
        if self.storage != FEATURE_MANIFEST_STORAGE:
            raise ValidationAppError(
                message="Unsupported feature manifest storage type.",
                detail={"storage": self.storage},
            )
        if len(self.shape) != 2:
            raise ValidationAppError(
                message="Feature manifest shape must be two-dimensional.",
                detail={"shape": self.shape},
            )
        if self.shape[0] != self.frame_count:
            raise ValidationAppError(
                message="Feature manifest frame_count and shape are inconsistent.",
                detail={"frame_count": self.frame_count, "shape": self.shape},
            )
        chunk_frames = sum(chunk.shape[0] for chunk in self.chunks)
        if chunk_frames != self.frame_count:
            raise ValidationAppError(
                message="Feature manifest chunk frame count is inconsistent.",
                detail={"frame_count": self.frame_count, "chunk_frames": chunk_frames},
            )


def load_feature_manifest(path: Path) -> FeatureManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = FeatureManifest.model_validate(payload)
        manifest.validate_contract()
        return manifest
    except ValidationAppError:
        raise
    except Exception as exc:
        raise ValidationAppError(
            message="Feature manifest could not be loaded.",
            detail={"path": str(path), "error": str(exc)},
        ) from exc


def dump_feature_manifest(path: Path, manifest: FeatureManifest) -> None:
    manifest.validate_contract()
    path.write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )


def iter_feature_chunk_arrays(
    manifest: FeatureManifest,
    storage: Any,
) -> Iterator[tuple[FeatureChunkManifest, np.ndarray]]:
    for chunk in manifest.chunks:
        chunk_path = storage.resolve_storage_path(chunk.path)
        with np.load(chunk_path) as payload:
            yield chunk, payload["features"]
