from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import ValidationAppError


@dataclass(frozen=True)
class FrameSample:
    frame_index: int
    timestamp_sec: float
    rgb_frame: object


class OpenCVVideoReader:
    def __init__(self, path: Path) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise ValidationAppError(
                message="OpenCV is not installed.",
                suggested_action="Install dependencies with setup.bat.",
            ) from exc

        self._cv2 = cv2
        self.path = path
        self.capture = cv2.VideoCapture(str(path))
        if not self.capture.isOpened():
            raise ValidationAppError(
                message="OpenCV could not open the video.",
                detail={"path": str(path)},
                suggested_action="Check codec support or create a proxy video with ffmpeg.",
            )

    def get_metadata(self) -> dict[str, float | int | None]:
        fps = self.capture.get(self._cv2.CAP_PROP_FPS) or None
        frame_count = self.capture.get(self._cv2.CAP_PROP_FRAME_COUNT) or None
        width = self.capture.get(self._cv2.CAP_PROP_FRAME_WIDTH) or None
        height = self.capture.get(self._cv2.CAP_PROP_FRAME_HEIGHT) or None
        return {
            "fps": float(fps) if fps else None,
            "frame_count": int(frame_count) if frame_count else None,
            "width": int(width) if width else None,
            "height": int(height) if height else None,
        }

    def seek(self, time_sec: float) -> None:
        self.capture.set(self._cv2.CAP_PROP_POS_MSEC, max(time_sec, 0.0) * 1000)

    def iter_frames(self, interval_sec: float) -> Iterator[FrameSample]:
        if interval_sec <= 0:
            raise ValidationAppError(
                message="Frame interval must be positive.",
                detail={"interval_sec": interval_sec},
            )
        next_timestamp = 0.0
        while True:
            ok, frame = self.capture.read()
            if not ok:
                break
            timestamp_ms = self.capture.get(self._cv2.CAP_PROP_POS_MSEC)
            timestamp_sec = timestamp_ms / 1000
            if timestamp_sec + 1e-6 < next_timestamp:
                continue
            frame_index = int(self.capture.get(self._cv2.CAP_PROP_POS_FRAMES)) - 1
            rgb_frame = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
            yield FrameSample(
                frame_index=max(frame_index, 0),
                timestamp_sec=timestamp_sec,
                rgb_frame=rgb_frame,
            )
            next_timestamp = timestamp_sec + interval_sec

    def close(self) -> None:
        self.capture.release()

    def __enter__(self) -> "OpenCVVideoReader":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
