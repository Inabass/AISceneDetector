from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExtractedFeatures:
    vectors: Any
    dtype: str
    shape: tuple[int, ...]
    extractor_metadata: dict[str, Any]


class FeatureExtractor(ABC):
    @abstractmethod
    def encode_frames(self, rgb_frames: list[Any]) -> ExtractedFeatures:
        raise NotImplementedError

    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        raise NotImplementedError
