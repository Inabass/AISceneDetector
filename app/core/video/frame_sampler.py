from collections.abc import Iterator
from pathlib import Path

from app.core.video.reader import FrameSample, OpenCVVideoReader


class FrameSampler:
    def sample(self, path: Path, interval_sec: float) -> Iterator[FrameSample]:
        with OpenCVVideoReader(path) as reader:
            yield from reader.iter_frames(interval_sec)
