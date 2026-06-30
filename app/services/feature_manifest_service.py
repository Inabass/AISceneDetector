import hashlib
from pathlib import Path
from typing import Iterator

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationAppError
from app.core.features.manifest import (
    FeatureChunkManifest,
    FeatureManifest,
    iter_feature_chunk_arrays,
    load_feature_manifest,
)
from app.models.feature import Feature
from app.repositories.feature_repository import FeatureRepository
from app.services.storage_service import StorageService


class FeatureManifestService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.storage = StorageService(settings)
        self.repository = FeatureRepository(db)

    def get_feature(self, feature_id: int) -> Feature:
        feature = self.repository.get(feature_id)
        if feature is None:
            raise NotFoundError(
                message="Feature was not found.",
                detail={"feature_id": feature_id},
            )
        return feature

    def load_manifest(self, feature_id: int, require_succeeded: bool = True) -> FeatureManifest:
        feature = self.get_feature(feature_id)
        if require_succeeded and feature.status != "succeeded":
            raise ValidationAppError(
                message="Feature is not ready for model generation.",
                detail={"feature_id": feature.id, "status": feature.status},
            )
        manifest_path = self.storage.resolve_storage_path(feature.path)
        self._verify_file_metadata(manifest_path, feature.file_size, feature.file_sha256)
        manifest = load_feature_manifest(manifest_path)
        for chunk in manifest.chunks:
            self.verify_chunk(chunk)
        return manifest

    def iter_feature_arrays(self, feature_id: int) -> Iterator[tuple[FeatureChunkManifest, np.ndarray]]:
        manifest = self.load_manifest(feature_id)
        yield from iter_feature_chunk_arrays(manifest, self.storage)

    def verify_chunk(self, chunk: FeatureChunkManifest) -> None:
        chunk_path = self.storage.resolve_storage_path(chunk.path)
        self._verify_file_metadata(chunk_path, chunk.size, chunk.sha256)

    def _verify_file_metadata(
        self,
        path: Path,
        expected_size: int | None,
        expected_sha256: str | None,
    ) -> None:
        if not path.is_file():
            raise ValidationAppError(
                message="Feature artifact file is missing.",
                detail={"path": str(path)},
            )
        if expected_size is not None and path.stat().st_size != expected_size:
            raise ValidationAppError(
                message="Feature artifact size mismatch.",
                detail={"path": str(path), "expected_size": expected_size, "actual_size": path.stat().st_size},
            )
        if expected_sha256 is not None and self._sha256_file(path) != expected_sha256:
            raise ValidationAppError(
                message="Feature artifact hash mismatch.",
                detail={"path": str(path)},
            )

    def _sha256_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
