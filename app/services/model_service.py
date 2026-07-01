import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationAppError
from app.db.session import SessionLocal
from app.db.unit_of_work import UnitOfWork
from app.models.feature import Feature
from app.models.model import AiModel, ModelVersion
from app.models.training_video import TrainingVideo
from app.repositories.feature_repository import FeatureRepository
from app.repositories.model_repository import ModelRepository
from app.services.job_service import JobService
from app.services.storage_service import StorageService


class ModelService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.storage = StorageService(settings)
        self.model_repository = ModelRepository(db)
        self.feature_repository = FeatureRepository(db)
        self.job_service = JobService(db)

    def create_model(self, name: str, description: str | None = None) -> AiModel:
        model = AiModel(name=name.strip(), description=description)
        if not model.name:
            raise ValidationAppError(
                message="Model name is required.",
                suggested_action="Enter a non-empty model name.",
            )
        with UnitOfWork(self.db):
            self.model_repository.add_model(model)
        self.db.refresh(model)
        return model

    def list_models(self) -> list[AiModel]:
        return self.model_repository.list_models()

    def get_model(self, model_id: int) -> AiModel:
        model = self.model_repository.get_model(model_id)
        if model is None:
            raise NotFoundError(
                message="Model was not found.",
                detail={"model_id": model_id},
            )
        return model

    def list_versions(self, model_id: int) -> list[ModelVersion]:
        self.get_model(model_id)
        return self.model_repository.list_versions(model_id)

    def get_active_version(self, model: AiModel) -> ModelVersion | None:
        return self.model_repository.get_active_version(model)

    def create_training_job(
        self,
        model_id: int,
        parent_version_id: int | None = None,
        threshold: float | None = None,
    ) -> int:
        model = self.get_model(model_id)
        if parent_version_id is not None:
            parent = self.model_repository.get_version(parent_version_id)
            if parent is None or parent.model_id != model.id:
                raise ValidationAppError(
                    message="Parent version does not belong to the model.",
                    detail={
                        "model_id": model_id,
                        "parent_version_id": parent_version_id,
                    },
                )
        job = self.job_service.create_job(
            "model_training",
            {
                "model_id": model_id,
                "parent_version_id": parent_version_id,
                "threshold": threshold,
            },
        )
        return job.id

    def rollback(self, model_id: int, version_id: int) -> AiModel:
        model = self.get_model(model_id)
        version = self.model_repository.get_version(version_id)
        if version is None or version.model_id != model.id:
            raise ValidationAppError(
                message="Rollback target version does not belong to the model.",
                detail={"model_id": model_id, "version_id": version_id},
            )
        if version.status != "ready":
            raise ValidationAppError(
                message="Rollback target version is not ready.",
                detail={"version_id": version_id, "status": version.status},
            )
        with UnitOfWork(self.db):
            model.active_version_id = version.id
        self.job_service.log(
            version.created_by_job_id,
            "info",
            "rollback",
            "Model active version was changed.",
            {"model_id": model.id, "active_version_id": version.id},
        ) if version.created_by_job_id else None
        self.db.refresh(model)
        return model

    def run_model_training_job(self, job_id: int) -> None:
        job_service = JobService(self.db)
        job = job_service._require_job(job_id)
        params = json.loads(job.params_json or "{}")
        try:
            job_service.start(job_id, "collecting_features")
            model = self.get_model(int(params["model_id"]))
            parent_version_id = params.get("parent_version_id")
            requested_threshold = params.get("threshold")
            features = self._collect_feature_set()
            positive_items = [item for item in features if item[1].label_type == "positive"]
            negative_items = [item for item in features if item[1].label_type == "negative"]
            if not positive_items:
                raise ValidationAppError(
                    message="At least one positive training feature is required.",
                    suggested_action="Upload a positive video and run feature extraction first.",
                )

            extractor = self._validate_extractor_compatibility(features)
            job_service.update_progress(job_id, 20, "computing_centroids")
            positive_centroid, positive_count = self._centroid(positive_items)
            negative_centroid: np.ndarray | None = None
            negative_count = 0
            if negative_items:
                negative_centroid, negative_count = self._centroid(negative_items)

            if job_service.is_cancel_requested(job_id):
                job_service.cancel(job_id, {"stage": "computing_centroids"})
                return

            job_service.update_progress(job_id, 55, "estimating_threshold")
            positive_scores = self._similarities(positive_items, positive_centroid)
            threshold = (
                float(requested_threshold)
                if requested_threshold is not None
                else self._initial_threshold(positive_scores)
            )
            negative_scores = (
                self._similarities(negative_items, positive_centroid)
                if negative_items
                else np.array([], dtype=np.float32)
            )
            margin = 0.05 if negative_items else 0.0

            version_number = self.model_repository.next_version_number(model.id)
            version_name = f"v{version_number}"
            temp_dir, final_dir = self._version_paths(model.id, version_name, job_id)
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            job_service.update_progress(job_id, 75, "saving_artifacts")
            artifact_path, feature_set_path, artifact_payload = self._write_artifacts(
                temp_dir=temp_dir,
                features=features,
                extractor=extractor,
                positive_centroid=positive_centroid,
                negative_centroid=negative_centroid,
                threshold=threshold,
                margin=margin,
                positive_count=positive_count,
                negative_count=negative_count,
                positive_scores=positive_scores,
                negative_scores=negative_scores,
            )

            if job_service.is_cancel_requested(job_id):
                shutil.rmtree(temp_dir, ignore_errors=True)
                job_service.cancel(job_id, {"stage": "saving_artifacts"})
                return

            if final_dir.exists():
                raise ValidationAppError(
                    message="Model version artifact directory already exists.",
                    detail={"path": self.storage.relative_path(final_dir)},
                    suggested_action="Retry the training job.",
                )
            final_dir.parent.mkdir(parents=True, exist_ok=True)
            temp_dir.replace(final_dir)
            artifact_rel = self.storage.relative_path(final_dir / artifact_path.name)
            feature_set_rel = self.storage.relative_path(final_dir / feature_set_path.name)

            version = ModelVersion(
                model_id=model.id,
                version=version_name,
                parent_version_id=parent_version_id,
                status="ready",
                artifact_path=artifact_rel,
                feature_set_path=feature_set_rel,
                thresholds_json=json.dumps(
                    artifact_payload["thresholds"],
                    ensure_ascii=True,
                ),
                metrics_json=json.dumps(artifact_payload["metrics"], ensure_ascii=True),
                extractor_json=json.dumps(extractor, ensure_ascii=True),
                matcher_json=json.dumps(artifact_payload["matcher"], ensure_ascii=True),
                cluster_json=json.dumps(artifact_payload["cluster"], ensure_ascii=True),
                classifier_json=json.dumps(
                    artifact_payload["classifier"],
                    ensure_ascii=True,
                ),
                created_by_job_id=job_id,
            )
            with UnitOfWork(self.db):
                self.model_repository.add_version(version)
                self.db.flush()
                model.active_version_id = version.id
            self.db.refresh(version)
            job_service.succeed(
                job_id,
                {
                    "model_id": model.id,
                    "model_version_id": version.id,
                    "version": version.version,
                    "artifact_path": version.artifact_path,
                    "positive_feature_count": len(positive_items),
                    "negative_feature_count": len(negative_items),
                },
            )
        except Exception as exc:
            code = getattr(exc, "error_code", exc.__class__.__name__)
            message = getattr(exc, "message", str(exc))
            job_service.fail(job_id, code, message)
            job_service.log(job_id, "error", "model_training", message)

    def _collect_feature_set(self) -> list[tuple[Feature, TrainingVideo]]:
        features = self.feature_repository.list_succeeded_training_features()
        valid_features = [
            item for item in features if self._feature_manifest_exists(item[0])
        ]
        if not valid_features:
            raise ValidationAppError(
                message="No completed training features were found.",
                suggested_action="Run feature extraction for training videos first.",
            )
        return valid_features

    def _feature_manifest_exists(self, feature: Feature) -> bool:
        try:
            return self.storage.resolve_storage_path(feature.path).exists()
        except Exception:
            return False

    def _validate_extractor_compatibility(
        self,
        features: list[tuple[Feature, TrainingVideo]],
    ) -> dict[str, object]:
        extractor = json.loads(features[0][0].extractor_json)
        for feature, video in features[1:]:
            current = json.loads(feature.extractor_json)
            if current != extractor:
                raise ValidationAppError(
                    message="Training features use mixed extractors.",
                    detail={
                        "source_video_id": video.id,
                        "feature_id": feature.id,
                    },
                    suggested_action="Regenerate features with the same extractor settings.",
                )
        return extractor

    def _centroid(self, items: list[tuple[Feature, TrainingVideo]]) -> tuple[np.ndarray, int]:
        total: np.ndarray | None = None
        count = 0
        for vectors in self._iter_vectors(items):
            batch = vectors.astype(np.float32, copy=False)
            batch_sum = batch.sum(axis=0, dtype=np.float64)
            total = batch_sum if total is None else total + batch_sum
            count += int(batch.shape[0])
        if total is None or count == 0:
            raise ValidationAppError(message="Feature set contains no vectors.")
        centroid = (total / count).astype(np.float32)
        norm = float(np.linalg.norm(centroid))
        if norm > 0:
            centroid = centroid / norm
        return centroid, count

    def _similarities(
        self,
        items: list[tuple[Feature, TrainingVideo]],
        centroid: np.ndarray,
    ) -> np.ndarray:
        scores: list[np.ndarray] = []
        for vectors in self._iter_vectors(items):
            batch = vectors.astype(np.float32, copy=False)
            scores.append(batch @ centroid)
        if not scores:
            return np.array([], dtype=np.float32)
        return np.concatenate(scores).astype(np.float32)

    def _iter_vectors(
        self,
        items: list[tuple[Feature, TrainingVideo]],
    ) -> Iterator[np.ndarray]:
        for feature, _video in items:
            manifest_path = self.storage.resolve_storage_path(feature.path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for chunk in manifest.get("chunks", []):
                chunk_path = self.storage.resolve_storage_path(str(chunk["path"]))
                yield np.load(chunk_path)

    def _initial_threshold(self, positive_scores: np.ndarray) -> float:
        if positive_scores.size == 0:
            return 0.75
        mean = float(np.mean(positive_scores))
        std = float(np.std(positive_scores))
        return max(0.1, min(0.95, mean - (2.0 * std)))

    def _version_paths(
        self,
        model_id: int,
        version: str,
        job_id: int,
    ) -> tuple[Path, Path]:
        temp_dir = self.storage.ensure_under_root(
            self.settings.temp_dir / f"model_{model_id}_{version}_job_{job_id}"
        )
        final_dir = self.storage.ensure_under_root(
            self.settings.models_dir / f"model_{model_id}" / version
        )
        return temp_dir, final_dir

    def _write_artifacts(
        self,
        temp_dir: Path,
        features: list[tuple[Feature, TrainingVideo]],
        extractor: dict[str, object],
        positive_centroid: np.ndarray,
        negative_centroid: np.ndarray | None,
        threshold: float,
        margin: float,
        positive_count: int,
        negative_count: int,
        positive_scores: np.ndarray,
        negative_scores: np.ndarray,
    ) -> tuple[Path, Path, dict[str, Any]]:
        artifact_path = temp_dir / "model.npz"
        feature_set_path = temp_dir / "feature_set.json"
        metadata_path = temp_dir / "metadata.json"
        np.savez_compressed(
            artifact_path,
            positive_centroid=positive_centroid.astype(np.float32),
            negative_centroid=(
                negative_centroid.astype(np.float32)
                if negative_centroid is not None
                else np.array([], dtype=np.float32)
            ),
        )
        feature_set = {
            "version": 1,
            "features": [
                {
                    "feature_id": feature.id,
                    "source_video_id": video.id,
                    "label_type": video.label_type,
                    "sha256": video.sha256,
                    "path": feature.path,
                    "frame_count": feature.frame_count,
                    "cache_key": feature.cache_key,
                }
                for feature, video in features
            ],
        }
        feature_set_path.write_text(
            json.dumps(feature_set, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        payload = {
            "version": 1,
            "thresholds": {
                "positive": threshold,
                "margin": margin,
            },
            "metrics": {
                "positive_vector_count": positive_count,
                "negative_vector_count": negative_count,
                "positive_score_mean": float(np.mean(positive_scores)),
                "positive_score_std": float(np.std(positive_scores)),
                "negative_score_mean": (
                    float(np.mean(negative_scores)) if negative_scores.size else None
                ),
                "negative_available": bool(negative_count),
            },
            "extractor": extractor,
            "matcher": {
                "type": "cosine_centroid",
                "positive_centroid_key": "positive_centroid",
                "negative_centroid_key": (
                    "negative_centroid" if negative_count else None
                ),
                "score_schema": "positive_similarity_minus_negative_margin",
            },
            "cluster": {
                "type": "single_centroid",
                "cluster_count": 1,
                "sample_counts": [positive_count],
                "thresholds": [threshold],
            },
            "classifier": {
                "classifier_type": "none",
                "reason": "Insufficient explicit classifier training in MVP model generation.",
            },
            "artifact_file": artifact_path.name,
            "feature_set_file": feature_set_path.name,
        }
        metadata_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        return artifact_path, feature_set_path, payload


def run_model_training_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        ModelService(db, get_settings()).run_model_training_job(job_id)
    finally:
        db.close()
