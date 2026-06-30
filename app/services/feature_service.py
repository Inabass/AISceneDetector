import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.core.ai.openclip_extractor import OpenCLIPFeatureExtractor
from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationAppError
from app.core.video.frame_sampler import FrameSampler
from app.db.session import SessionLocal
from app.db.unit_of_work import UnitOfWork
from app.models.feature import Feature
from app.models.training_video import TrainingVideo
from app.repositories.feature_repository import FeatureRepository
from app.repositories.training_video_repository import TrainingVideoRepository
from app.services.gpu_service import GpuService
from app.services.job_service import JobService
from app.services.storage_service import StorageService


class FeatureService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.storage = StorageService(settings)
        self.video_repository = TrainingVideoRepository(db)
        self.feature_repository = FeatureRepository(db)
        self.job_service = JobService(db)

    def create_training_feature_job(
        self,
        video_id: int,
        frame_interval_sec: float | None = None,
        batch_size: int | None = None,
    ) -> int:
        video = self._require_extractable_video(video_id)
        GpuService(self.settings).require_cuda_available()

        interval = frame_interval_sec or self.settings.default_frame_interval_sec
        batch = batch_size or self.settings.default_training_batch_size
        cache_key = self.cache_key(video, interval)
        cached = self.feature_repository.get_succeeded_by_cache_key(cache_key)
        job = self.job_service.create_job(
            "training_feature_extraction",
            {
                "video_id": video_id,
                "frame_interval_sec": interval,
                "batch_size": batch,
                "cache_key": cache_key,
                "cached_feature_id": cached.id if cached else None,
            },
        )
        if cached is not None:
            self.job_service.succeed(
                job.id,
                {"feature_id": cached.id, "cache_hit": True},
            )
        return job.id

    def run_training_feature_job(self, job_id: int) -> None:
        job_service = JobService(self.db)
        job = job_service._require_job(job_id)
        params = json.loads(job.params_json or "{}")
        if params.get("cached_feature_id"):
            return

        try:
            job_service.start(job_id, "loading_video")
            video = self._require_extractable_video(int(params["video_id"]))
            interval = float(params["frame_interval_sec"])
            batch_size = int(params["batch_size"])
            cache_key = str(params["cache_key"])

            video_path = self.storage.resolve_storage_path(video.path)
            extractor = OpenCLIPFeatureExtractor(self.settings)
            sampler = FrameSampler()

            feature_chunks: list[np.ndarray] = []
            frame_indices: list[int] = []
            timestamps: list[float] = []
            frame_batch: list[Any] = []
            processed = 0

            job_service.update_progress(job_id, 5, "sampling_frames")
            for sample in sampler.sample(video_path, interval):
                frame_batch.append(sample.rgb_frame)
                frame_indices.append(sample.frame_index)
                timestamps.append(sample.timestamp_sec)
                if len(frame_batch) >= batch_size:
                    feature_chunks.append(extractor.encode_frames(frame_batch).vectors)
                    processed += len(frame_batch)
                    frame_batch = []
                    job_service.update_progress(job_id, 50, "extracting_features")
            if frame_batch:
                feature_chunks.append(extractor.encode_frames(frame_batch).vectors)
                processed += len(frame_batch)

            if not feature_chunks:
                raise ValidationAppError(
                    message="No frames were sampled from the training video.",
                    detail={"video_id": video.id, "frame_interval_sec": interval},
                    suggested_action="Check video readability or lower the frame interval.",
                )

            vectors = np.concatenate(feature_chunks, axis=0)
            feature_path = self._feature_output_path(video, cache_key)
            feature_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                feature_path,
                features=vectors,
                frame_indices=np.asarray(frame_indices, dtype=np.int64),
                timestamps=np.asarray(timestamps, dtype=np.float32),
            )
            feature = Feature(
                source_video_id=video.id,
                kind="training_frame_features",
                path=self.storage.relative_path(feature_path),
                dtype=str(vectors.dtype),
                shape_json=json.dumps(list(vectors.shape), ensure_ascii=True),
                frame_interval_sec=interval,
                extractor_json=json.dumps(extractor.metadata(), ensure_ascii=True),
                cache_key=cache_key,
                status="succeeded",
                frame_count=processed,
                created_by_job_id=job_id,
            )
            with UnitOfWork(self.db):
                self.feature_repository.add(feature)
            self.db.refresh(feature)
            job_service.succeed(
                job_id,
                {
                    "feature_id": feature.id,
                    "cache_hit": False,
                    "frame_count": processed,
                    "feature_path": feature.path,
                },
            )
        except Exception as exc:
            code = getattr(exc, "error_code", exc.__class__.__name__)
            message = getattr(exc, "message", str(exc))
            job_service.fail(job_id, code, message)
            job_service.log(job_id, "error", "feature_extraction", message)

    def cache_key(self, video: TrainingVideo, frame_interval_sec: float) -> str:
        payload = {
            "sha256": video.sha256,
            "frame_interval_sec": frame_interval_sec,
            "extractor": "openclip",
            "model_name": self.settings.openclip_model_name,
            "pretrained": self.settings.openclip_pretrained,
            "feature_dtype": self.settings.openclip_feature_dtype,
        }
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _require_extractable_video(self, video_id: int) -> TrainingVideo:
        video = self.video_repository.get(video_id)
        if video is None:
            raise NotFoundError(
                message="Training video was not found.",
                detail={"video_id": video_id},
            )
        if video.processing_status == "WARNING_OPENCV_UNREADABLE":
            raise ValidationAppError(
                message="Training video is not readable by OpenCV.",
                detail={
                    "video_id": video_id,
                    "processing_status": video.processing_status,
                },
                suggested_action="Re-upload a codec OpenCV can read or create a proxy video.",
            )
        if video.processing_status != "READY":
            raise ValidationAppError(
                message="Training video is not ready for feature extraction.",
                detail={
                    "video_id": video_id,
                    "processing_status": video.processing_status,
                },
            )
        return video

    def _feature_output_path(self, video: TrainingVideo, cache_key: str) -> Path:
        return self.storage.ensure_under_root(
            self.settings.features_dir / f"training_video_{video.id}" / f"{cache_key}.npz"
        )


def run_training_feature_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        from app.core.config import get_settings

        FeatureService(db, get_settings()).run_training_feature_job(job_id)
    finally:
        db.close()
