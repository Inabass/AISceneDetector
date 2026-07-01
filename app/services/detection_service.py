import hashlib
import json
from dataclasses import dataclass
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
from app.models.detection import DetectionResult, DetectionSegment
from app.models.model import ModelVersion
from app.repositories.detection_repository import DetectionRepository
from app.repositories.model_repository import ModelRepository
from app.services.gpu_service import GpuService
from app.services.job_service import JobService
from app.services.settings_service import SettingsService
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
        self.settings_service = SettingsService(db, settings)

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

        interval = frame_interval_sec or float(
            self.settings_service.get_effective(
                "default_frame_interval_sec",
                self.settings.default_frame_interval_sec,
            )
        )
        if interval <= 0:
            raise ValidationAppError(
                message="frame_interval_sec must be positive.",
                detail={"frame_interval_sec": interval},
            )
        batch = batch_size or int(
            self.settings_service.get_effective(
                "default_detection_batch_size",
                self.settings.default_detection_batch_size,
            )
        )
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
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        timeline["segments"] = [
            self._segment_to_payload(segment)
            for segment in self.repository.list_segments(detection.id)
        ]
        return timeline

    def run_detection_job(self, job_id: int) -> None:
        job_service = JobService(self.db)
        job = job_service._require_job(job_id)
        params = json.loads(job.params_json or "{}")
        timeline_path: Path | None = None
        temp_timeline_path: Path | None = None
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
            temp_timeline_path = timeline_path.with_suffix(".json.tmp")
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

            header = self._timeline_header(
                detection,
                model_version,
                threshold,
                margin,
                interval,
            )
            with _TimelineWriter(temp_timeline_path, header) as writer:
                job_service.update_progress(job_id, 5, "sampling_frames")
                for sample in sampler.sample(video_path, interval):
                    if job_service.is_cancel_requested(job_id):
                        summary = stats.summary("cancelled")
                        writer.finish(summary)
                        temp_timeline_path.replace(timeline_path)
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
                            writer,
                            stats,
                            job_id,
                            job_service,
                            current_batch_size,
                        )
                        frame_batch = []
                        sample_batch = []
                        job_service.update_progress(
                            job_id,
                            self._progress_from_timestamp(
                                sample.timestamp_sec,
                                detection.duration,
                            ),
                            "running_inference",
                        )
                if frame_batch:
                    current_batch_size = self._process_detection_batch(
                        extractor,
                        frame_batch,
                        sample_batch,
                        model_payload,
                        threshold,
                        margin,
                        writer,
                        stats,
                        job_id,
                        job_service,
                        current_batch_size,
                    )
                summary = stats.summary("succeeded")
                writer.finish(summary)
            temp_timeline_path.replace(timeline_path)

            with UnitOfWork(self.db):
                detection.status = "succeeded"
                detection.timeline_path = self.storage.relative_path(timeline_path)
                detection.summary_json = json.dumps(summary, ensure_ascii=True)
            segments = self.generate_segments(detection.id)
            summary = {**summary, "segment_count": len(segments)}
            with UnitOfWork(self.db):
                detection.summary_json = json.dumps(summary, ensure_ascii=True)
            job_service.succeed(
                job_id,
                {
                    "detection_id": detection.id,
                    "timeline_path": detection.timeline_path,
                    "processed_frames": stats.processed_frames,
                    "positive_frames": stats.positive_frames,
                    "segment_count": len(segments),
                },
            )
        except Exception as exc:
            if temp_timeline_path is not None and temp_timeline_path.exists():
                temp_timeline_path.unlink()
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
            except Exception:
                pass
            job_service.fail(job_id, code, message)
            job_service.log(job_id, "error", "detection", message)

    def list_segments(self, detection_id: int) -> list[DetectionSegment]:
        detection = self.get_detection(detection_id)
        segments = self.repository.list_segments(detection_id)
        self._ensure_segment_thumbnails(detection, segments)
        return self.repository.list_segments(detection_id)

    def generate_segments(self, detection_id: int) -> list[DetectionSegment]:
        detection = self.get_detection(detection_id)
        if not detection.timeline_path:
            return []
        timeline = self.read_timeline(detection_id)
        points = timeline.get("points") or []
        if not points:
            with UnitOfWork(self.db):
                self.repository.delete_segments(detection.id)
            return []

        frame_interval = float(
            timeline.get("frame_interval_sec")
            or self.settings.default_frame_interval_sec
        )
        threshold = float(timeline.get("threshold"))
        margin = float(timeline.get("margin") or 0.0)
        settings = self._segment_settings()
        candidates = self._build_segment_candidates(
            points=points,
            frame_interval=frame_interval,
            threshold=threshold,
            margin=margin,
            video_duration=detection.duration,
            settings=settings,
        )
        with UnitOfWork(self.db):
            self.repository.delete_segments(detection.id)
            saved = []
            for index, candidate in enumerate(candidates, start=1):
                metadata = dict(candidate.metadata)
                metadata.update(
                    self._segment_thumbnail_metadata(
                        detection=detection,
                        segment_index=index,
                        timestamp_sec=candidate.representative_timestamp_sec,
                    )
                )
                segment = DetectionSegment(
                    detection_result_id=detection.id,
                    segment_index=index,
                    start_sec=candidate.start_sec,
                    end_sec=candidate.end_sec,
                    padded_start_sec=candidate.padded_start_sec,
                    padded_end_sec=candidate.padded_end_sec,
                    duration_sec=candidate.duration_sec,
                    score=candidate.score,
                    max_score=candidate.max_score,
                    average_score=candidate.average_score,
                    representative_timestamp_sec=candidate.representative_timestamp_sec,
                    start_frame_index=candidate.start_frame_index,
                    end_frame_index=candidate.end_frame_index,
                    status="detected",
                    metadata_json=json.dumps(metadata, ensure_ascii=True),
                )
                self.repository.add_segment(segment)
                saved.append(segment)
        return self.repository.list_segments(detection.id)

    def _ensure_segment_thumbnails(
        self,
        detection: DetectionResult,
        segments: list[DetectionSegment],
    ) -> None:
        changed = False
        for segment in segments:
            metadata = json.loads(segment.metadata_json)
            if metadata.get("thumbnail_path"):
                continue
            metadata.update(
                self._segment_thumbnail_metadata(
                    detection=detection,
                    segment_index=segment.segment_index,
                    timestamp_sec=segment.representative_timestamp_sec,
                )
            )
            segment.metadata_json = json.dumps(metadata, ensure_ascii=True)
            changed = True
        if changed:
            with UnitOfWork(self.db):
                pass

    def _segment_thumbnail_metadata(
        self,
        detection: DetectionResult,
        segment_index: int,
        timestamp_sec: float,
    ) -> dict[str, object]:
        try:
            thumbnail_path = self._write_segment_thumbnail(
                detection=detection,
                segment_index=segment_index,
                timestamp_sec=timestamp_sec,
            )
            thumbnail_rel = self.storage.relative_path(thumbnail_path)
            return {
                "thumbnail_path": thumbnail_rel,
                "thumbnail_url": f"/media/{thumbnail_rel}",
            }
        except Exception as exc:
            return {"thumbnail_error": getattr(exc, "message", str(exc))}

    def _write_segment_thumbnail(
        self,
        detection: DetectionResult,
        segment_index: int,
        timestamp_sec: float,
    ) -> Path:
        video_path = self.storage.resolve_storage_path(detection.source_video_path)
        thumbnail_path = self.storage.ensure_under_root(
            self.settings.thumbnails_dir
            / "detections"
            / f"detection_{detection.id}"
            / f"segment_{segment_index:03d}.jpg"
        )
        if thumbnail_path.exists():
            return thumbnail_path
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        with OpenCVVideoReader(video_path) as reader:
            reader.seek(timestamp_sec)
            ok, frame = reader.capture.read()
            if not ok:
                raise ValidationAppError(
                    message="Could not read segment thumbnail frame.",
                    detail={
                        "detection_id": detection.id,
                        "segment_index": segment_index,
                        "timestamp_sec": timestamp_sec,
                    },
                )
            height, width = frame.shape[:2]
            if width > 640:
                scale = 640 / width
                frame = reader._cv2.resize(
                    frame,
                    (640, max(1, int(height * scale))),
                    interpolation=reader._cv2.INTER_AREA,
                )
            ok = reader._cv2.imwrite(str(thumbnail_path), frame)
            if not ok:
                raise ValidationAppError(
                    message="Could not write segment thumbnail.",
                    detail={"path": str(thumbnail_path)},
                )
        return thumbnail_path

    def _segment_settings(self) -> dict[str, float]:
        return {
            "smoothing_window_sec": float(
                self.settings_service.get_effective(
                    "default_smoothing_window_sec",
                    self.settings.default_smoothing_window_sec,
                )
            ),
            "merge_gap_sec": float(
                self.settings_service.get_effective(
                    "default_merge_gap_sec",
                    self.settings.default_merge_gap_sec,
                )
            ),
            "padding_sec": float(
                self.settings_service.get_effective(
                    "default_padding_sec",
                    self.settings.default_padding_sec,
                )
            ),
            "min_segment_duration_sec": float(
                self.settings_service.get_effective(
                    "default_min_segment_duration_sec",
                    self.settings.default_min_segment_duration_sec,
                )
            ),
            "max_segment_duration_sec": float(
                self.settings_service.get_effective(
                    "default_max_segment_duration_sec",
                    self.settings.default_max_segment_duration_sec,
                )
            ),
        }

    def _build_segment_candidates(
        self,
        points: list[dict[str, Any]],
        frame_interval: float,
        threshold: float,
        margin: float,
        video_duration: float | None,
        settings: dict[str, float],
    ) -> list["_SegmentCandidate"]:
        smoothed = self._smooth_points(
            points,
            frame_interval,
            settings["smoothing_window_sec"],
        )
        ranges = self._positive_ranges(smoothed, threshold, margin)
        candidates = [
            self._candidate_from_points(
                range_points,
                frame_interval,
                video_duration,
                settings,
            )
            for range_points in ranges
        ]
        candidates = [
            candidate
            for candidate in candidates
            if candidate.duration_sec >= settings["min_segment_duration_sec"]
        ]
        candidates = self._merge_candidates(
            candidates,
            settings["merge_gap_sec"],
            video_duration,
        )
        return self._split_long_candidates(
            candidates,
            settings["max_segment_duration_sec"],
            video_duration,
        )

    def _smooth_points(
        self,
        points: list[dict[str, Any]],
        frame_interval: float,
        smoothing_window_sec: float,
    ) -> list[dict[str, Any]]:
        window = max(1, int(round(smoothing_window_sec / max(frame_interval, 1e-6))))
        radius = max(0, window // 2)
        confidences = [float(point.get("confidence") or 0.0) for point in points]
        smoothed: list[dict[str, Any]] = []
        for index, point in enumerate(points):
            start = max(0, index - radius)
            end = min(len(points), index + radius + 1)
            value = sum(confidences[start:end]) / max(1, end - start)
            confidence = float(point.get("confidence") or 0.0)
            smoothed.append(
                {
                    **point,
                    "smoothed_confidence": value,
                    "detection_score": max(confidence, value),
                }
            )
        return smoothed

    def _positive_ranges(
        self,
        points: list[dict[str, Any]],
        threshold: float,
        margin: float,
    ) -> list[list[dict[str, Any]]]:
        ranges: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        for point in points:
            margin_score = point.get("margin_score")
            margin_ok = margin_score is None or float(margin_score) >= margin
            is_positive = float(point["detection_score"]) >= threshold and margin_ok
            if is_positive:
                current.append(point)
            elif current:
                ranges.append(current)
                current = []
        if current:
            ranges.append(current)
        return ranges

    def _candidate_from_points(
        self,
        points: list[dict[str, Any]],
        frame_interval: float,
        video_duration: float | None,
        settings: dict[str, float],
    ) -> "_SegmentCandidate":
        start_sec = float(points[0]["timestamp_sec"])
        end_sec = float(points[-1]["timestamp_sec"]) + frame_interval
        if video_duration:
            end_sec = min(end_sec, video_duration)
        scores = [float(point["detection_score"]) for point in points]
        max_index = max(range(len(points)), key=lambda index: scores[index])
        average_score = sum(scores) / len(scores)
        max_score = scores[max_index]
        padded_start = max(0.0, start_sec - settings["padding_sec"])
        padded_end = end_sec + settings["padding_sec"]
        if video_duration:
            padded_end = min(padded_end, video_duration)
        return _SegmentCandidate(
            start_sec=start_sec,
            end_sec=end_sec,
            padded_start_sec=padded_start,
            padded_end_sec=max(padded_end, padded_start),
            duration_sec=max(0.0, padded_end - padded_start),
            score=average_score,
            max_score=max_score,
            average_score=average_score,
            representative_timestamp_sec=float(points[max_index]["timestamp_sec"]),
            start_frame_index=_int_or_none(points[0].get("frame_index")),
            end_frame_index=_int_or_none(points[-1].get("frame_index")),
            points=points,
            metadata={
                "raw_start_sec": start_sec,
                "raw_end_sec": end_sec,
                "point_count": len(points),
                "smoothing_window_sec": settings["smoothing_window_sec"],
                "padding_sec": settings["padding_sec"],
            },
        )

    def _merge_candidates(
        self,
        candidates: list["_SegmentCandidate"],
        merge_gap_sec: float,
        video_duration: float | None,
    ) -> list["_SegmentCandidate"]:
        if not candidates:
            return []
        merged = [candidates[0]]
        for candidate in candidates[1:]:
            previous = merged[-1]
            if candidate.start_sec - previous.end_sec <= merge_gap_sec:
                merged[-1] = self._merge_two_candidates(previous, candidate, video_duration)
            else:
                merged.append(candidate)
        return merged

    def _merge_two_candidates(
        self,
        left: "_SegmentCandidate",
        right: "_SegmentCandidate",
        video_duration: float | None,
    ) -> "_SegmentCandidate":
        points = left.points + right.points
        scores = [float(point["detection_score"]) for point in points]
        max_index = max(range(len(points)), key=lambda index: scores[index])
        average_score = sum(scores) / len(scores)
        padded_end = right.padded_end_sec
        if video_duration:
            padded_end = min(padded_end, video_duration)
        return _SegmentCandidate(
            start_sec=left.start_sec,
            end_sec=right.end_sec,
            padded_start_sec=left.padded_start_sec,
            padded_end_sec=padded_end,
            duration_sec=max(0.0, padded_end - left.padded_start_sec),
            score=average_score,
            max_score=max(scores),
            average_score=average_score,
            representative_timestamp_sec=float(points[max_index]["timestamp_sec"]),
            start_frame_index=left.start_frame_index,
            end_frame_index=right.end_frame_index,
            points=points,
            metadata={**left.metadata, "merged": True, "point_count": len(points)},
        )

    def _split_long_candidates(
        self,
        candidates: list["_SegmentCandidate"],
        max_duration_sec: float,
        video_duration: float | None,
    ) -> list["_SegmentCandidate"]:
        if max_duration_sec <= 0:
            return candidates
        output: list[_SegmentCandidate] = []
        for candidate in candidates:
            if candidate.duration_sec <= max_duration_sec:
                output.append(candidate)
                continue
            chunk_start = candidate.padded_start_sec
            while chunk_start < candidate.padded_end_sec:
                chunk_end = min(chunk_start + max_duration_sec, candidate.padded_end_sec)
                output.append(
                    _SegmentCandidate(
                        start_sec=max(candidate.start_sec, chunk_start),
                        end_sec=min(candidate.end_sec, chunk_end),
                        padded_start_sec=chunk_start,
                        padded_end_sec=chunk_end,
                        duration_sec=max(0.0, chunk_end - chunk_start),
                        score=candidate.score,
                        max_score=candidate.max_score,
                        average_score=candidate.average_score,
                        representative_timestamp_sec=candidate.representative_timestamp_sec,
                        start_frame_index=candidate.start_frame_index,
                        end_frame_index=candidate.end_frame_index,
                        points=candidate.points,
                        metadata={
                            **candidate.metadata,
                            "split_by_max_duration": True,
                            "max_segment_duration_sec": max_duration_sec,
                        },
                    )
                )
                chunk_start = chunk_end
        return output

    def _segment_to_payload(self, segment: DetectionSegment) -> dict[str, object]:
        return {
            "id": segment.id,
            "detection_result_id": segment.detection_result_id,
            "segment_index": segment.segment_index,
            "start_sec": segment.start_sec,
            "end_sec": segment.end_sec,
            "padded_start_sec": segment.padded_start_sec,
            "padded_end_sec": segment.padded_end_sec,
            "duration_sec": segment.duration_sec,
            "score": segment.score,
            "max_score": segment.max_score,
            "average_score": segment.average_score,
            "representative_timestamp_sec": segment.representative_timestamp_sec,
            "start_frame_index": segment.start_frame_index,
            "end_frame_index": segment.end_frame_index,
            "status": segment.status,
            "metadata": json.loads(segment.metadata_json),
        }

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
        writer: "_TimelineWriter",
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
            margin_score = (
                positive_score - negative_score
                if negative_score is not None
                else None
            )
            confidence = self._clamp01(positive_score)
            is_positive = positive_score >= threshold and (
                margin_score is None or margin_score >= margin
            )
            point = {
                "frame_index": frame_index,
                "timestamp_sec": timestamp_sec,
                "positive_score": positive_score,
                "negative_score": negative_score,
                "margin_score": margin_score,
                "matcher_score": positive_score,
                "confidence": confidence,
                "threshold": threshold,
                "margin": margin,
                "score_schema": "cosine_centroid_v1",
                "is_positive": is_positive,
            }
            stats.add(point)
            writer.write_point(point)
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

    def _timeline_header(
        self,
        detection: DetectionResult,
        model_version: ModelVersion,
        threshold: float,
        margin: float,
        interval: float,
    ) -> dict[str, object]:
        return {
            "version": 1,
            "detection_id": detection.id,
            "model_version_id": model_version.id,
            "threshold": threshold,
            "margin": margin,
            "frame_interval_sec": interval,
            "score_schema": "cosine_centroid_v1",
            "score_fields": {
                "positive_score": "Cosine similarity against the positive centroid.",
                "negative_score": "Cosine similarity against the negative centroid, or null.",
                "margin_score": "positive_score - negative_score, or null.",
                "confidence": "positive_score clipped to the 0.0-1.0 range.",
            },
        }

    def _progress_from_timestamp(
        self,
        timestamp_sec: float,
        duration: float | None,
    ) -> int:
        if not duration or duration <= 0:
            return 50
        return max(5, min(95, int((timestamp_sec / duration) * 90) + 5))

    def _clamp01(self, value: float) -> float:
        return max(0.0, min(1.0, value))

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


@dataclass
class _SegmentCandidate:
    start_sec: float
    end_sec: float
    padded_start_sec: float
    padded_end_sec: float
    duration_sec: float
    score: float
    max_score: float
    average_score: float
    representative_timestamp_sec: float
    start_frame_index: int | None
    end_frame_index: int | None
    points: list[dict[str, Any]]
    metadata: dict[str, object]


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


class _TimelineWriter:
    def __init__(self, path: Path, header: dict[str, object]) -> None:
        self.path = path
        self.header = header
        self.output: TextIO | None = None
        self.has_points = False
        self.finished = False

    def __enter__(self) -> "_TimelineWriter":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.output = self.path.open("w", encoding="utf-8")
        self.output.write("{")
        for index, (key, value) in enumerate(self.header.items()):
            if index:
                self.output.write(",")
            self.output.write(json.dumps(str(key), ensure_ascii=True))
            self.output.write(":")
            self.output.write(json.dumps(value, ensure_ascii=True))
        self.output.write(',"points":[')
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.output is None:
            return
        if exc_type is None and not self.finished:
            self.finish({"status": "failed", "error": "Timeline was not finalized."})
        self.output.close()

    def write_point(self, point: dict[str, object]) -> None:
        if self.output is None:
            raise RuntimeError("Timeline writer is not open.")
        if self.has_points:
            self.output.write(",")
        self.output.write(json.dumps(point, ensure_ascii=True))
        self.has_points = True

    def finish(self, summary: dict[str, object]) -> None:
        if self.output is None:
            raise RuntimeError("Timeline writer is not open.")
        if self.finished:
            return
        self.output.write(
            "],\"summary\":"
            + json.dumps(summary, ensure_ascii=True)
            + "}"
        )
        self.finished = True


def run_detection_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        DetectionService(db, get_settings()).run_detection_job(job_id)
    finally:
        db.close()
