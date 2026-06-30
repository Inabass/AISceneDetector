import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.core.ai.openclip_extractor import OpenCLIPFeatureExtractor
from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationAppError
from app.core.features.manifest import FeatureManifest, dump_feature_manifest
from app.core.video.frame_sampler import FrameSampler
from app.db.session import SessionLocal
from app.db.unit_of_work import UnitOfWork
from app.models.feature import Feature
from app.models.training_video import TrainingVideo
from app.repositories.feature_repository import FeatureRepository
from app.repositories.training_video_repository import TrainingVideoRepository
from app.services.gpu_service import GpuService
from app.services.job_service import JobCancelledError, JobService
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
        cached = self._valid_cached_feature(cache_key)
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
                {"feature_id": cached.id, "cache_hit": True, "integrity_checked": True},
            )
        return job.id

    def run_training_feature_job(self, job_id: int) -> None:
        job_service = JobService(self.db)
        job = job_service._require_job(job_id)
        params = json.loads(job.params_json or "{}")
        if params.get("cached_feature_id"):
            return

        checkpoint: dict[str, Any] = {}
        temp_paths: list[Path] = []
        try:
            job_service.start(job_id, "loading_video")
            video = self._require_extractable_video(int(params["video_id"]))
            interval = float(params["frame_interval_sec"])
            max_batch_size = max(1, int(params["batch_size"]))
            cache_key = str(params["cache_key"])

            video_path = self.storage.resolve_storage_path(video.path)
            extractor = OpenCLIPFeatureExtractor(self.settings)
            sampler = FrameSampler()

            output_dir = self._feature_output_dir(video, cache_key)
            output_dir.mkdir(parents=True, exist_ok=True)
            chunks_dir = output_dir / "chunks"
            chunks_dir.mkdir(parents=True, exist_ok=True)

            resume_checkpoint = params.get("resume_checkpoint") or {}
            chunks = self._validated_resume_chunks(resume_checkpoint)
            processed = int(resume_checkpoint.get("processed_frames", 0)) if chunks else 0
            feature_dim: int | None = int(chunks[-1]["shape"][1]) if chunks else None
            dtype: str | None = str(chunks[-1]["dtype"]) if chunks else None
            current_batch_size = int(resume_checkpoint.get("batch_size_current", max_batch_size))
            current_batch_size = max(1, min(current_batch_size, max_batch_size))
            skipped = 0

            frame_batch: list[Any] = []
            index_batch: list[int] = []
            timestamp_batch: list[float] = []

            job_service.update_progress(job_id, 5, "sampling_frames", self._checkpoint(chunks, processed, current_batch_size))
            for sample in sampler.sample(video_path, interval):
                job_service.raise_if_cancel_requested(job_id)
                if skipped < processed:
                    skipped += 1
                    continue
                frame_batch.append(sample.rgb_frame)
                index_batch.append(sample.frame_index)
                timestamp_batch.append(sample.timestamp_sec)
                if len(frame_batch) >= current_batch_size:
                    result = self._encode_save_chunk(
                        extractor=extractor,
                        frames=frame_batch,
                        frame_indices=index_batch,
                        timestamps=timestamp_batch,
                        chunks_dir=chunks_dir,
                        chunk_index=len(chunks),
                        job_id=job_id,
                        requested_batch_size=current_batch_size,
                    )
                    current_batch_size = result["next_batch_size"]
                    chunks.append(result["chunk"])
                    temp_paths.extend(result["temp_paths"])
                    processed += len(frame_batch)
                    feature_dim = int(result["chunk"]["shape"][1])
                    dtype = str(result["chunk"]["dtype"])
                    frame_batch = []
                    index_batch = []
                    timestamp_batch = []
                    checkpoint = self._checkpoint(chunks, processed, current_batch_size)
                    job_service.update_progress(job_id, 50, "extracting_features", checkpoint)

            if frame_batch:
                job_service.raise_if_cancel_requested(job_id)
                result = self._encode_save_chunk(
                    extractor=extractor,
                    frames=frame_batch,
                    frame_indices=index_batch,
                    timestamps=timestamp_batch,
                    chunks_dir=chunks_dir,
                    chunk_index=len(chunks),
                    job_id=job_id,
                    requested_batch_size=current_batch_size,
                )
                current_batch_size = result["next_batch_size"]
                chunks.append(result["chunk"])
                temp_paths.extend(result["temp_paths"])
                processed += len(frame_batch)
                feature_dim = int(result["chunk"]["shape"][1])
                dtype = str(result["chunk"]["dtype"])
                checkpoint = self._checkpoint(chunks, processed, current_batch_size)
                job_service.update_progress(job_id, 80, "saving_feature_manifest", checkpoint)

            if not chunks or feature_dim is None or dtype is None:
                raise ValidationAppError(
                    message="No frames were sampled from the training video.",
                    detail={"video_id": video.id, "frame_interval_sec": interval},
                    suggested_action="Check video readability or lower the frame interval.",
                )

            manifest_path = output_dir / "manifest.json"
            manifest = FeatureManifest(
                status="succeeded",
                chunks=chunks,
                frame_count=processed,
                shape=[processed, feature_dim],
                dtype=dtype,
                cache_key=cache_key,
                source_video_id=video.id,
                extractor=extractor.metadata(),
            )
            dump_feature_manifest(manifest_path, manifest)
            manifest_hash = self._sha256_file(manifest_path)
            manifest_size = manifest_path.stat().st_size

            feature = Feature(
                source_video_id=video.id,
                kind="training_frame_features",
                path=self.storage.relative_path(manifest_path),
                dtype=dtype,
                shape_json=json.dumps([processed, feature_dim], ensure_ascii=True),
                frame_interval_sec=interval,
                extractor_json=json.dumps(extractor.metadata(), ensure_ascii=True),
                cache_key=cache_key,
                status="succeeded",
                frame_count=processed,
                created_by_job_id=job_id,
            )
            if hasattr(feature, "file_sha256"):
                feature.file_sha256 = manifest_hash
            if hasattr(feature, "file_size"):
                feature.file_size = manifest_size
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
                    "chunk_count": len(chunks),
                    "batch_size_final": current_batch_size,
                    "manifest_sha256": manifest_hash,
                },
            )
        except JobCancelledError:
            for path in temp_paths:
                path.unlink(missing_ok=True)
            if "chunks" in locals() and "output_dir" in locals() and chunks:
                self._record_partial_feature(
                    video=video,
                    output_dir=output_dir,
                    chunks=chunks,
                    processed=processed,
                    feature_dim=feature_dim or 0,
                    dtype=dtype or self.settings.openclip_feature_dtype,
                    interval=interval,
                    extractor_metadata=extractor.metadata(),
                    cache_key=cache_key,
                    job_id=job_id,
                )
            job_service.cancel(job_id, checkpoint)
            job_service.log(job_id, "info", "feature_extraction", "Feature extraction job was cancelled.")
        except Exception as exc:
            for path in temp_paths:
                path.unlink(missing_ok=True)
            code = getattr(exc, "error_code", exc.__class__.__name__)
            message = getattr(exc, "message", str(exc))
            job_service.fail(job_id, code, message)
            job_service.log(job_id, "error", "feature_extraction", message)
        finally:
            if "extractor" in locals():
                extractor.release()

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

    def _encode_save_chunk(
        self,
        extractor: OpenCLIPFeatureExtractor,
        frames: list[Any],
        frame_indices: list[int],
        timestamps: list[float],
        chunks_dir: Path,
        chunk_index: int,
        job_id: int,
        requested_batch_size: int,
    ) -> dict[str, Any]:
        batch_size = min(max(1, requested_batch_size), len(frames))
        while True:
            try:
                parts = []
                for start in range(0, len(frames), batch_size):
                    self.job_service.raise_if_cancel_requested(job_id)
                    parts.append(extractor.encode_frames(frames[start : start + batch_size]).vectors)
                vectors = parts[0] if len(parts) == 1 else np.concatenate(parts, axis=0)
                break
            except RuntimeError as exc:
                if not extractor.is_out_of_memory_error(exc) or not self.settings.auto_batch_reduction or batch_size <= 1:
                    raise
                new_batch_size = max(1, batch_size // 2)
                extractor.clear_memory_after_oom()
                self.job_service.log(
                    job_id,
                    "warning",
                    "feature_extraction",
                    "CUDA out of memory; reducing feature extraction batch size.",
                    {"old_batch_size": batch_size, "new_batch_size": new_batch_size},
                )
                batch_size = new_batch_size

        chunk_path = chunks_dir / f"chunk_{chunk_index:06d}.npz"
        temp_path = chunk_path.with_suffix(".tmp.npz")
        np.savez_compressed(
            temp_path,
            features=vectors,
            frame_indices=np.asarray(frame_indices, dtype=np.int64),
            timestamps=np.asarray(timestamps, dtype=np.float32),
        )
        temp_path.replace(chunk_path)
        sha256 = self._sha256_file(chunk_path)
        return {
            "next_batch_size": batch_size,
            "temp_paths": [temp_path],
            "chunk": {
                "path": self.storage.relative_path(chunk_path),
                "sha256": sha256,
                "size": chunk_path.stat().st_size,
                "shape": list(vectors.shape),
                "dtype": str(vectors.dtype),
                "first_frame_index": int(frame_indices[0]),
                "last_frame_index": int(frame_indices[-1]),
                "first_timestamp_sec": float(timestamps[0]),
                "last_timestamp_sec": float(timestamps[-1]),
            },
        }

    def _valid_cached_feature(self, cache_key: str) -> Feature | None:
        feature = self.feature_repository.get_succeeded_by_cache_key(cache_key)
        if feature is None:
            return None
        try:
            manifest_path = self.storage.resolve_storage_path(feature.path)
            if not manifest_path.is_file():
                return None
            if hasattr(feature, "file_size") and feature.file_size is not None and manifest_path.stat().st_size != feature.file_size:
                return None
            if hasattr(feature, "file_sha256") and feature.file_sha256 and self._sha256_file(manifest_path) != feature.file_sha256:
                return None
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for chunk in manifest.get("chunks", []):
                chunk_path = self.storage.resolve_storage_path(chunk["path"])
                if not chunk_path.is_file():
                    return None
                if chunk_path.stat().st_size != int(chunk["size"]):
                    return None
                if self._sha256_file(chunk_path) != chunk["sha256"]:
                    return None
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
        return feature


    def _record_partial_feature(
        self,
        video: TrainingVideo,
        output_dir: Path,
        chunks: list[dict[str, Any]],
        processed: int,
        feature_dim: int,
        dtype: str,
        interval: float,
        extractor_metadata: dict[str, Any],
        cache_key: str,
        job_id: int,
    ) -> None:
        partial_manifest_path = output_dir / "partial_manifest.json"
        manifest = FeatureManifest(
            status="partial",
            chunks=chunks,
            frame_count=processed,
            shape=[processed, feature_dim],
            dtype=dtype,
            cache_key=cache_key,
            source_video_id=video.id,
            extractor=extractor_metadata,
        )
        dump_feature_manifest(partial_manifest_path, manifest)
        feature = Feature(
            source_video_id=video.id,
            kind="training_frame_features",
            path=self.storage.relative_path(partial_manifest_path),
            dtype=dtype,
            shape_json=json.dumps([processed, feature_dim], ensure_ascii=True),
            frame_interval_sec=interval,
            extractor_json=json.dumps(extractor_metadata, ensure_ascii=True),
            cache_key=cache_key,
            status="partial",
            frame_count=processed,
            created_by_job_id=job_id,
        )
        if hasattr(feature, "file_sha256"):
            feature.file_sha256 = self._sha256_file(partial_manifest_path)
        if hasattr(feature, "file_size"):
            feature.file_size = partial_manifest_path.stat().st_size
        with UnitOfWork(self.db):
            self.feature_repository.add(feature)


    def _validated_resume_chunks(self, checkpoint: dict[str, Any]) -> list[dict[str, Any]]:
        chunks = checkpoint.get("chunks")
        if not isinstance(chunks, list):
            return []
        valid_chunks: list[dict[str, Any]] = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                return []
            try:
                chunk_path = self.storage.resolve_storage_path(str(chunk["path"]))
                if not chunk_path.is_file():
                    return []
                if chunk_path.stat().st_size != int(chunk["size"]):
                    return []
                if self._sha256_file(chunk_path) != str(chunk["sha256"]):
                    return []
                valid_chunks.append(chunk)
            except (KeyError, OSError, TypeError, ValueError):
                return []
        return valid_chunks

    def _checkpoint(self, chunks: list[dict[str, Any]], processed: int, batch_size: int) -> dict[str, Any]:
        return {
            "processed_frames": processed,
            "chunk_count": len(chunks),
            "chunks": chunks,
            "last_chunk": chunks[-1] if chunks else None,
            "batch_size_current": batch_size,
        }

    def _require_extractable_video(self, video_id: int) -> TrainingVideo:
        video = self.video_repository.get(video_id)
        if video is None:
            raise NotFoundError(message="Training video was not found.", detail={"video_id": video_id})
        if video.processing_status == "WARNING_OPENCV_UNREADABLE":
            raise ValidationAppError(
                message="Training video is not readable by OpenCV.",
                detail={"video_id": video_id, "processing_status": video.processing_status},
                suggested_action="Re-upload a codec OpenCV can read or create a proxy video.",
            )
        if video.processing_status != "READY":
            raise ValidationAppError(
                message="Training video is not ready for feature extraction.",
                detail={"video_id": video_id, "processing_status": video.processing_status},
            )
        return video

    def _feature_output_dir(self, video: TrainingVideo, cache_key: str) -> Path:
        return self.storage.ensure_under_root(self.settings.features_dir / f"training_video_{video.id}" / cache_key)

    def _sha256_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


def run_training_feature_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        from app.core.config import get_settings

        FeatureService(db, get_settings()).run_training_feature_job(job_id)
    finally:
        db.close()
