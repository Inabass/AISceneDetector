from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VideoMetadata:
    duration: float | None
    fps: float | None
    frame_count: int | None
    width: int | None
    height: int | None
    codec: str | None
    pixel_format: str | None
    bitrate: int | None
    rotation: int | None
    stream_count: int | None
    has_audio: bool | None
    raw: dict[str, Any]
    opencv: dict[str, Any] | None = None
