from typing import Any

from pydantic import BaseModel

from app.schemas.common import ApiResponse


class FeatureChunkData(BaseModel):
    path: str
    sha256: str
    size: int
    shape: list[int]
    dtype: str
    first_frame_index: int
    last_frame_index: int
    first_timestamp_sec: float
    last_timestamp_sec: float


class FeatureManifestData(BaseModel):
    schema_version: int
    storage: str
    status: str
    chunks: list[FeatureChunkData]
    frame_count: int
    shape: list[int]
    dtype: str
    cache_key: str
    source_video_id: int
    extractor: dict[str, Any]


class FeatureManifestResponse(ApiResponse[FeatureManifestData]):
    pass
