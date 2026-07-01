import hashlib
import json
from pathlib import Path
from typing import Any, TextIO

import numpy as np
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.ai.openclip_extractor import OpenCLIPFeatureExtractor, is_cuda_oom
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationAppError
from app.core.video.frame_sampler import FrameSampler
from app.core.video.probe import FFprobeVideoProbe
from app.core.video.reader import OpenCVVideoReader
from app.db.session import SessionLocal
from app.db.unit_of_work import UnitOfWork
from app.models.detection import DetectionResult
from app.models.model import ModelVersion
from app.repositories.detection_repository import DetectionRepository
from app.repositories.model_repository import ModelRepository
from app.services.gpu_service import GpuService
from app.services.job_service import JobService
from app.services.storage_service import StorageService
from app.services.video_service import _looks_like_known_video_container, _looks_like_text


class DetectionService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.storage = StorageService(settings)
        self.repository = DetectionRepository(db)
        self.model_repository = ModelRepository(db)
        self.job_service = JobService(db)
        self.probe = FFprobeVideoProbe(settings)

    async def create_detection_job(
        self,
        upload: UploadFile,
        model_id: int | None = None,
        model_version_id: int | None = None,
        frame_interval_sec: float | None = None,
        batch_size: int | None = None,
        threshold: float | None = None,
    ) -> int:
        if not upload.filename:
            raise ValidationAppError(
                message="Upload filename is required.",
                suggested_action="Upload a video file with a valid file name.",
            )
        model_version = self._resolve_model_version(model_id, model_version_id)
        GpuService(self.settings).require_cuda_available()

        interval = frame_interval_sec or self.settings.default_frame_interval_sec
        if interval <= 0:
            raise ValidationAppError(
                message="frame_interval_sec must be positive.",
                detail={"frame_interval_sec": interval},
            )
        batch = batch_size or self.settings.default_detection_batch_size
        if batch <= 0:
            raise ValidationAppError(
                message="batch_size must be positive.",
                detail={"batch_size": batch},
            )

        extension = self.storage.validate_video_extension(upload.filename)
        destination = self.storage.upload_path(upload.filename)
        file_size, sha256 = await self._save_upload(upload, destination)

        try:
            self._validate_content_sniff(destination, extension)
            metadata = self.probe.probe(destination)
            try:
                with OpenCVVideoReader(destination):
                    pass
            except ValidationAppError as exc:
                raise ValidationAppError(
                    message="Detection video is not readable by OpenCV.",
                    detail={"path": self.storage.relative_path(destination)},
                    suggested_action="Create an OpenCV-readable proxy video with ffmpeg.",
                ) from exc

            settings_payload = {
                "frame_interval_sec": interval,
                "batch_size": batch,
                "threshold": threshold,
            }
            detection = DetectionResult(
                source_video_path=self.storage.relative_path(destination),
                source_filename=upload.filename,
                source_sha256=sha256,
                file_size=file_size,
                duration=metadata.duration,
                fps=metadata.fps,
                frame_count=metadata.frame_count,
                width=metadata.width,
                height=metadata.height,
                model_version_id=model_version.id,
                settings_json=json.dumps(settings_payload, ensure_ascii=True),
                timeline_path=None,
                summary_json=None,
                status="queued",
                job_id=None,
            )
            with UnitOfWork(self.db):
                self.repository.add(detection)
            self.db.refresh(detection)

            job = self.job_service.create_job(
                "detection",
                {
                    "detection_id": detection.id,
                    "model_version_id": model_version.id,
                    "frame_interval_sec": interval,
                    "batch_size": batch,
                    "threshold": threshold,
                },
            )
            with UnitOfWork(self.db):
                detection.job_id = job.id
            return job.id
        except Exception:
            if destination.exists():
                destination.unlink()
            raise

    def get_detection(self, detection_id: int) -> DetectionResult:
        detection = self.repository.get(detection_id)
        if detection is None:
            raise NotFoundError(
                message="Detection result was not found.",
                detail={"detection_id": detection_id},
            )
        return detection

    def list_detections(self, limit: int = 50) -> list[DetectionResult]:
        return self.repository.list_recent(limit)

    def read_timeline(self, detection_id: int) -> dict[str, object]:
        detection = self.get_detection(detection_id)
        if not detection.timeline_path:
            raise ValidationAppError(
                message="Detection timeline is not available yet.",
                detail={"detection_id": detection_id, "status": detection.status},
                suggested_action="Wait for the detection job to finish.",
            )
        timeline_path = self.storage.resolve_storage_path(detection.timeline_path)
        return json.loads(timeline_path.read_text(encoding="utf-8"))

    def run_detection_job(self, job_id: int) -> None:
        job_service = JobService(self.db)
        job = job_service._require_job(job_id)
        params = json.loads(job.params_json or "{}")
        timeline_path: Path | None = None
        try:
            job_service.start(job_id, "loading_detection")
            detection = self.get_detection(int(params["detection_id"]))
            model_version = self._require_model_version(int(params["model_version_id"]))
            model_payload = self._load_model_payload(model_version)
            threshold = (
                float(params["threshold"])
                if params.get("threshold") is not None
                else float(model_payload["thresholds"]["positive"])
            )
            margin = float(model_payload["thresholds"].get("margin") or 0.0)
            batch_size = max(1, int(params["batch_size"]))
            interval = float(params["frame_interval_sec"])

            video_path = self.storage.resolve_storage_path(detection.source_video_path)
            timeline_path = self._timeline_output_path(detection.id, job_id)
            timeline_path.parent.mkdir(parents=True, exist_ok=True)
            extractor = OpenCLIPFeatureExtractor(self.settings)
            if extractor.metadata() != model_payload["extractor"]:
                raise ValidationAppError(
                    message="Current extractor settings do not match the model version.",
                    detail={
                        "current_extractor": extractor.metadata(),
                        "model_extractor": model_payload["extractor"],
                    },
                    suggested_action="Use the same OpenCLIP settings or train a new model version.",
                )
            sampler = FrameSampler()

            with UnitOfWork(self.db):
                detection.status = "running"

            stats = _DetectionStats()
            frame_batch: list[Any] = []
            sample_batch: list[tuple[int, float]] = []
            current_batch_size = batch_size

            with timeline_path.open("w", encoding="utf-8") as output:
                self._write_timeline_header(
                    output,
                    detection,
                    model_version,
                    threshold,
                    margin,
                    interval,
                )
                job_service.update_progress(job_id, 5, "sampling_frames")
                for sample in sampler.sample(video_path, interval):
                    if job_service.is_cancel_requested(job_id):
                        self._finish_timeline(output, stats.summary("cancelled"))
                        self._mark_detection_cancelled(detection, timeline_path, stats)
                        job_service.cancel(
                            job_id,
                            {
                                "detection_id": detection.id,
                                "timeline_path": self.storage.relative_path(timeline_path),
                                "processed_frames": stats.processed_frames,
                            },
                        )
                        return

                    frame_batch.append(sample.rgb_frame)
                    sample_batch.append((sample.frame_index, sample.timestamp_sec))
                    if len(frame_batch) >= current_batch_size:
                        current_batch_size = self._process_detection_batch(
                            extractor,
                            frame_batch,
                            sample_batch,
                            model_payload,
                            threshold,
                            margin,
                            output,
                            stats,
                            job_id,
                            job_service,
                            current_batch_size,
                        )
                        frame_batch = []
                        sample_batch = []
                        job_service.update_progress(job_id, 50, "running_inference")
                if frame_batch:
                    current_batch_size = self._process_detection_batch(
                        extractor,
                        frame_batch,
                        sample_batch,
                        model_payload,
                        threshold,
                        margin,
                        output,
                        stats,
                        job_id,
                        job_service,
                        current_batch_size,
                    )
                summary = stats.summary("succeeded")
                self._finish_timeline(output, summary)

            with UnitOfWork(self.db):
                detection.status = "succeeded"
                detection.timeline_path = self.storage.relative_path(timeline_path)
                detection.summary_json = json.dumps(summary, ensure_ascii=True)
            job_service.succeed(
                job_id,
                {
                    "detection_id": detection.id,
                    "timeline_path": detection.timeline_path,
                    "processed_frames": stats.processed_frames,
                    "positive_frames": stats.positive_frames,
                },
            )
        except Exception as exc:
            code = getattr(exc, "error_code", exc.__class__.__name__)
            message = getattr(exc, "message", str(exc))
            try:
                detection = self.get_detection(int(params.get("detection_id", 0)))
                with UnitOfWork(self.db):
                    detection.status = "failed"
                    detection.summary_json = json.dumps(
                        {"status": "failed", "error": message},
                        ensure_ascii=True,
                    )
                    if timeline_path and timeline_path.exists():
                        detection.timeline_path = self.storage.relative_path(timeline_path)
            except Exception:
                pass
            job_service.fail(job_id, code, message)
            job_service.log(job_id, "error", "detection", message)

    def _resolve_model_version(
        self,
        model_id: int | None,
        model_version_id: int | None,
    ) -> ModelVersion:
        if model_version_id is not None:
            version = self.model_repository.get_version(model_version_id)
            if version is None:
                raise NotFoundError(
                    message="Model version was not found.",
                    detail={"model_version_id": model_version_id},
                )
            if version.status != "ready":
                raise ValidationAppError(
                    message="Model version is not ready.",
                    detail={"model_version_id": version.id, "status": version.status},
                )
            return version
        if model_id is None:
            raise ValidationAppError(
                message="model_id or model_version_id is required.",
                suggested_action="Select a model or a model version.",
            )
        model = self.model_repository.get_model(model_id)
        if model is None:
            raise NotFoundError(message="Model was not found.", detail={"model_id": model_id})
        version = self.model_repository.get_active_version(model)
        if version is None:
            raise ValidationAppError(
                message="Model has no active version.",
                detail={"model_id": model_id},
                suggested_action="Train the model first.",
            )
        if version.status != "ready":
            raise ValidationAppError(
                message="Active model version is not ready.",
                detail={"model_version_id": version.id, "status": version.status},
            )
        return version

    def _require_model_version(self, model_version_id: int) -> ModelVersion:
        version = self.model_repository.get_version(model_version_id)
        if version is None:
            raise NotFoundError(
                message="Model version was not found.",
                detail={"model_version_id": model_version_id},
            )
        return version

    def _load_model_payload(self, model_version: ModelVersion) -> dict[str, Any]:
        artifact_path = self.storage.resolve_storage_path(model_version.artifact_path)
        if not artifact_path.exists():
            raise ValidationAppError(
                message="Model artifact file was not found.",
                detail={"artifact_path": model_version.artifact_path},
                suggested_action="Re-train the model version.",
            )
        with np.load(artifact_path) as artifact:
            positive_centroid = artifact["positive_centroid"].astype(np.float32)
            negative_centroid = artifact["negative_centroid"].astype(np.float32)
        return {
            "positive_centroid": positive_centroid,
            "negative_centroid": negative_centroid if negative_centroid.size else None,
            "thresholds": json.loads(model_version.thresholds_json),
            "matcher": json.loads(model_version.matcher_json),
            "extractor": json.loads(model_version.extractor_json),
        }

    async def _save_upload(self, upload: UploadFile, destination: Path) -> tuple[int, str]:
        hasher = hashlib.sha256()
        total_size = 0
        try:
            with destination.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    total_size += len(chunk)
                    if total_size > self.settings.max_upload_size_bytes:
                        raise ValidationAppError(
                            message="Uploaded file is too large.",
                            detail={
                                "max_upload_size_bytes": self.settings.max_upload_size_bytes,
                            },
                            suggested_action="Use a smaller file or increase the upload limit.",
                        )
                    hasher.update(chunk)
                    output.write(chunk)
        except Exception:
            if destination.exists():
                destination.unlink()
            raise
        finally:
            await upload.close()

        if total_size == 0:
            if destination.exists():
                destination.unlink()
            raise ValidationAppError(
                message="Uploaded file is empty.",
                suggested_action="Upload a non-empty video file.",
            )
        return total_size, hasher.hexdigest()

    def _validate_content_sniff(self, path: Path, extension: str) -> None:
        head = path.read_bytes()[:512]
        if not head:
            raise ValidationAppError(
                message="Uploaded file is empty.",
                suggested_action="Upload a non-empty video file.",
            )
        if _looks_like_known_video_container(head):
            return
        if _looks_like_text(head):
            raise ValidationAppError(
                message="Uploaded file does not look like a video.",
                detail={"extension": extension},
                suggested_action="Upload a valid video file instead of a text file.",
            )

    def _timeline_output_path(self, detection_id: int, job_id: int) -> Path:
        return self.storage.ensure_under_root(
            self.settings.outputs_dir
            / "detections"
            / f"detection_{detection_id}"
            / f"timeline_job_{job_id}.json"
        )

    def _process_detection_batch(
        self,
        extractor: OpenCLIPFeatureExtractor,
        frame_batch: list[Any],
        sample_batch: list[tuple[int, float]],
        model_payload: dict[str, Any],
        threshold: float,
        margin: float,
        output: TextIO,
        stats: "_DetectionStats",
        job_id: int,
        job_service: JobService,
        current_batch_size: int,
    ) -> int:
        vectors, current_batch_size = self._encode_with_batch_reduction(
            extractor,
            frame_batch,
            current_batch_size,
            job_id,
            job_service,
        )
        positive_centroid = model_payload["positive_centroid"]
        negative_centroid = model_payload["negative_centroid"]
        positive_scores = vectors.astype(np.float32, copy=False) @ positive_centroid
        negative_scores = (
            vectors.astype(np.float32, copy=False) @ negative_centroid
            if negative_centroid is not None
            else np.zeros_like(positive_scores)
        )
        for index, (frame_index, timestamp_sec) in enumerate(sample_batch):
            positive_score = float(positive_scores[index])
            negative_score = float(negative_scores[index]) if negative_centroid is not None else None
            confidence = (
                positive_score - max(0.0, float(negative_score or 0.0) - positive_score)
                if negative_centroid is not None
                else positive_score
            )
            is_positive = positive_score >= threshold and (
                negative_score is None or positive_score - negative_score >= margin
            )
            point = {
                "frame_index": frame_index,
                "timestamp_sec": timestamp_sec,
                "positive_score": positive_score,
                "negative_score": negative_score,
                "confidence": confidence,
                "threshold": threshold,
                "is_positive": is_positive,
            }
            stats.add(point)
            self._write_timeline_point(output, point, stats.processed_frames > 1)
        return current_batch_size

    def _encode_with_batch_reduction(
        self,
        extractor: OpenCLIPFeatureExtractor,
        frame_batch: list[Any],
        current_batch_size: int,
        job_id: int,
        job_service: JobService,
    ) -> tuple[np.ndarray, int]:
        outputs: list[np.ndarray] = []
        index = 0
        while index < len(frame_batch):
            size = min(current_batch_size, len(frame_batch) - index)
            while True:
                try:
                    subset = frame_batch[index : index + size]
                    outputs.append(extractor.encode_frames(subset).vectors)
                    index += size
                    break
                except Exception as exc:
                    if not is_cuda_oom(exc) or size <= 1:
                        raise
                    extractor.clear_memory_after_oom()
                    size = max(1, size // 2)
                    current_batch_size = size
                    job_service.log(
                        job_id,
                        "warning",
                        "auto_batch_reduction",
                        "CUDA OOM detected. Detection batch size was reduced.",
                        {"new_batch_size": current_batch_size},
                    )
        return np.concatenate(outputs, axis=0), current_batch_size

    def _write_timeline_header(
        self,
        output: TextIO,
        detection: DetectionResult,
        model_version: ModelVersion,
        threshold: float,
        margin: float,
        interval: float,
    ) -> None:
        header = {
            "version": 1,
            "detection_id": detection.id,
            "model_version_id": model_version.id,
            "threshold": threshold,
            "margin": margin,
            "frame_interval_sec": interval,
        }
        output.write(json.dumps({**header, "points": []}, ensure_ascii=True)[:-2])

    def _write_timeline_point(
        self,
        output: TextIO,
        point: dict[str, object],
        needs_comma: bool,
    ) -> None:
        if needs_comma:
            output.write(",")
        output.write(json.dumps(point, ensure_ascii=True))

    def _finish_timeline(self, output: TextIO, summary: dict[str, object]) -> None:
        output.write(
            "],\"summary\":"
            + json.dumps(summary, ensure_ascii=True)
            + "}"
        )

    def _mark_detection_cancelled(
        self,
        detection: DetectionResult,
        timeline_path: Path,
        stats: "_DetectionStats",
    ) -> None:
        with UnitOfWork(self.db):
            detection.status = "cancelled"
            detection.timeline_path = self.storage.relative_path(timeline_path)
            detection.summary_json = json.dumps(
                stats.summary("cancelled"),
                ensure_ascii=True,
            )


class _DetectionStats:
    def __init__(self) -> None:
        self.processed_frames = 0
        self.positive_frames = 0
        self.max_confidence: float | None = None
        self.confidence_sum = 0.0

    def add(self, point: dict[str, object]) -> None:
        confidence = float(point["confidence"])
        self.processed_frames += 1
        self.confidence_sum += confidence
        if bool(point["is_positive"]):
            self.positive_frames += 1
        if self.max_confidence is None or confidence > self.max_confidence:
            self.max_confidence = confidence

    def summary(self, status: str) -> dict[str, object]:
        average_confidence = (
            self.confidence_sum / self.processed_frames
            if self.processed_frames
            else None
        )
        return {
            "status": status,
            "processed_frames": self.processed_frames,
            "positive_frames": self.positive_frames,
            "max_confidence": self.max_confidence,
            "average_confidence": average_confidence,
        }


def run_detection_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        DetectionService(db, get_settings()).run_detection_job(job_id)
    finally:
        db.close()
