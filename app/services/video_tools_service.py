import shutil
import subprocess
from dataclasses import dataclass

from app.core.config import Settings
from app.core.errors import ValidationAppError


@dataclass(frozen=True)
class VideoToolStatus:
    name: str
    configured_path: str | None
    resolved_path: str | None
    available: bool
    version: str | None
    error: str | None = None


class VideoToolsService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def ffmpeg_status(self) -> VideoToolStatus:
        return self._status("ffmpeg", self.settings.ffmpeg_path)

    def ffprobe_status(self) -> VideoToolStatus:
        return self._status("ffprobe", self.settings.ffprobe_path)

    def all_statuses(self) -> list[VideoToolStatus]:
        return [self.ffmpeg_status(), self.ffprobe_status()]

    def require_available(self) -> list[VideoToolStatus]:
        statuses = self.all_statuses()
        missing = [status for status in statuses if not status.available]
        if missing:
            raise ValidationAppError(
                message="Required video tools were not found.",
                detail={
                    "tools": [status.__dict__ for status in statuses],
                },
                suggested_action=(
                    "Install ffmpeg/ffprobe or configure AISD_FFMPEG_PATH and "
                    "AISD_FFPROBE_PATH."
                ),
            )
        return statuses

    def _status(self, name: str, configured_path: str | None) -> VideoToolStatus:
        resolved = configured_path or shutil.which(name)
        if not resolved:
            return VideoToolStatus(
                name=name,
                configured_path=configured_path,
                resolved_path=None,
                available=False,
                version=None,
                error="not_found",
            )

        try:
            completed = subprocess.run(
                [resolved, "-version"],
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            return VideoToolStatus(
                name=name,
                configured_path=configured_path,
                resolved_path=resolved,
                available=False,
                version=None,
                error=str(exc),
            )

        first_line = completed.stdout.splitlines()[0] if completed.stdout else None
        return VideoToolStatus(
            name=name,
            configured_path=configured_path,
            resolved_path=resolved,
            available=completed.returncode == 0,
            version=first_line,
            error=completed.stderr.strip() or None if completed.returncode != 0 else None,
        )
