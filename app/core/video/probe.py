import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.core.video.metadata import VideoMetadata


class FFprobeVideoProbe:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def probe(self, path: Path) -> VideoMetadata:
        ffprobe = self._ffprobe_command()
        command = [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise ValidationAppError(
                message="ffprobe execution failed.",
                detail={"path": str(path), "error": str(exc)},
                suggested_action="Check the ffprobe path in Settings or PATH.",
            ) from exc

        if completed.returncode != 0:
            raise ValidationAppError(
                message="Video validation failed.",
                detail={
                    "path": str(path),
                    "stderr": completed.stderr.strip(),
                },
                suggested_action="Check whether the video file is readable by ffprobe.",
            )

        try:
            raw = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValidationAppError(
                message="ffprobe returned invalid JSON.",
                detail={"path": str(path)},
                suggested_action="Check ffprobe installation and video file integrity.",
            ) from exc

        return self._metadata_from_raw(raw)

    def _ffprobe_command(self) -> str:
        if self.settings.ffprobe_path:
            return self.settings.ffprobe_path
        found = shutil.which("ffprobe")
        if found:
            return found
        raise ValidationAppError(
            message="ffprobe was not found.",
            detail={"ffprobe_path": self.settings.ffprobe_path},
            suggested_action="Install ffmpeg/ffprobe or configure AISD_FFPROBE_PATH.",
        )

    def _metadata_from_raw(self, raw: dict[str, Any]) -> VideoMetadata:
        streams = raw.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        if video_stream is None:
            raise ValidationAppError(
                message="No video stream was found.",
                detail={"stream_count": len(streams)},
                suggested_action="Upload a file that contains a video stream.",
            )

        duration = _float_or_none(
            video_stream.get("duration") or raw.get("format", {}).get("duration")
        )
        fps = _fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))
        frame_count = _int_or_none(video_stream.get("nb_frames"))
        width = _int_or_none(video_stream.get("width"))
        height = _int_or_none(video_stream.get("height"))
        codec = video_stream.get("codec_name")
        pixel_format = video_stream.get("pix_fmt")
        bitrate = _int_or_none(
            video_stream.get("bit_rate") or raw.get("format", {}).get("bit_rate")
        )
        rotation = _rotation(video_stream)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)

        if duration is not None and duration <= 0:
            raise ValidationAppError(
                message="Video duration must be positive.",
                detail={"duration": duration},
                suggested_action="Upload a readable video with positive duration.",
            )

        return VideoMetadata(
            duration=duration,
            fps=fps,
            frame_count=frame_count,
            width=width,
            height=height,
            codec=codec,
            pixel_format=pixel_format,
            bitrate=bitrate,
            rotation=rotation,
            stream_count=len(streams),
            has_audio=has_audio,
            raw=raw,
        )


def _float_or_none(value: Any) -> float | None:
    if value in (None, "N/A"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value in (None, "N/A"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _fps(value: Any) -> float | None:
    if value in (None, "N/A", "0/0"):
        return None
    try:
        fps = float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return None
    return fps if fps > 0 else None


def _rotation(video_stream: dict[str, Any]) -> int | None:
    tags = video_stream.get("tags") or {}
    rotation = _int_or_none(tags.get("rotate"))
    if rotation is not None:
        return rotation
    side_data = video_stream.get("side_data_list") or []
    for item in side_data:
        rotation = _int_or_none(item.get("rotation"))
        if rotation is not None:
            return rotation
    return None
