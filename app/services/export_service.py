import json
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationAppError
from app.db.session import SessionLocal
from app.db.unit_of_work import UnitOfWork
from app.models.detection import DetectionResult, DetectionSegment
from app.models.export import Export
from app.repositories.detection_repository import DetectionRepository
from app.repositories.export_repository import ExportRepository
from app.services.job_service import JobService
from app.services.storage_service import StorageService
from app.services.video_tools_service import VideoToolsService


class ExportService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.storage = StorageService(settings)
        self.export_repository = ExportRepository(db)
        self.detection_repository = DetectionRepository(db)
        self.job_service = JobService(db)

    def create_export_job(
        self,
        detection_id: int,
        segment_ids: list[int] | None = None,
        mode: str = "copy",
    ) -> int:
        if mode not in {"copy", "reencode"}:
            raise ValidationAppError(
                message="Export mode must be copy or reencode.",
                detail={"mode": mode},
            )
        VideoToolsService(self.settings).require_available()
        detection = self._require_detection(detection_id)
        if detection.status != "succeeded":
            raise ValidationAppError(
                message="Detection result is not ready for export.",
                detail={"detection_id": detection_id, "status": detection.status},
            )
        segments = self._select_segments(detection_id, segment_ids)
        if not segments:
            raise ValidationAppError(
                message="No detection segments are available for export.",
                detail={"detection_id": detection_id, "segment_ids": segment_ids},
                suggested_action="Run detection again or lower the detection threshold.",
            )
        job = self.job_service.create_job(
            "export",
            {
                "detection_id": detection_id,
                "segment_ids": [segment.id for segment in segments],
                "mode": mode,
            },
        )
        with UnitOfWork(self.db):
            for segment in segments:
                self.export_repository.add(
                    Export(
                        detection_result_id=detection_id,
                        segment_id=segment.id,
                        mode=mode,
                        status="queued",
                        output_path=None,
                        thumbnail_path=None,
                        preview_path=None,
                        ffmpeg_args_json=None,
                        error_message=None,
                        asset_error_message=None,
                        job_id=job.id,
                    )
                )
        return job.id

    def get_export(self, export_id: int) -> Export:
        export = self.export_repository.get(export_id)
        if export is None:
            raise NotFoundError(
                message="Export was not found.",
                detail={"export_id": export_id},
            )
        return export

    def list_exports(self, limit: int = 50) -> list[Export]:
        return self.export_repository.list_recent(limit)

    def run_export_job(self, job_id: int) -> None:
        job_service = JobService(self.db)
        job = job_service._require_job(job_id)
        params = json.loads(job.params_json or "{}")
        try:
            job_service.start(job_id, "preparing_export")
            detection = self._require_detection(int(params["detection_id"]))
            source_path = self.storage.resolve_storage_path(detection.source_video_path)
            exports = self.export_repository.list_by_job(job_id)
            if not exports:
                raise ValidationAppError(
                    message="No export records were found for the job.",
                    detail={"job_id": job_id},
                )
            completed = 0
            failed = 0
            for index, export in enumerate(exports, start=1):
                if job_service.is_cancel_requested(job_id):
                    job_service.cancel(
                        job_id,
                        {"completed": completed, "failed": failed},
                    )
                    return
                segment = self._require_segment(int(export.segment_id))
                try:
                    output_path = self._output_path(detection, segment, export.mode)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    command = self._ffmpeg_command(
                        source_path=source_path,
                        output_path=output_path,
                        start_sec=segment.padded_start_sec,
                        end_sec=segment.padded_end_sec,
                        mode=export.mode,
                    )
                    with UnitOfWork(self.db):
                        export.status = "running"
                        export.ffmpeg_args_json = json.dumps(command, ensure_ascii=True)
                    self._run_ffmpeg(command)
                    asset_error_message = None
                    thumbnail_path = None
                    preview_path = None
                    try:
                        thumbnail_path = self._thumbnail_path(detection, segment)
                        preview_path = self._preview_path(detection, segment)
                        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
                        preview_path.parent.mkdir(parents=True, exist_ok=True)
                        self._run_ffmpeg(
                            self._thumbnail_command(
                                source_path=source_path,
                                output_path=thumbnail_path,
                                timestamp_sec=segment.representative_timestamp_sec,
                            )
                        )
                        self._run_ffmpeg(
                            self._preview_command(
                                source_path=source_path,
                                output_path=preview_path,
                                start_sec=segment.padded_start_sec,
                                end_sec=segment.padded_end_sec,
                            )
                        )
                    except Exception as exc:
                        asset_error_message = getattr(exc, "message", str(exc))
                        job_service.log(
                            job_id,
                            "warning",
                            "export_assets",
                            asset_error_message,
                            {"export_id": export.id, "segment_id": export.segment_id},
                        )
                    with UnitOfWork(self.db):
                        export.status = "succeeded"
                        export.output_path = self.storage.relative_path(output_path)
                        export.thumbnail_path = (
                            self.storage.relative_path(thumbnail_path)
                            if thumbnail_path and thumbnail_path.exists()
                            else None
                        )
                        export.preview_path = (
                            self.storage.relative_path(preview_path)
                            if preview_path and preview_path.exists()
                            else None
                        )
                        export.error_message = None
                        export.asset_error_message = asset_error_message
                    completed += 1
                except Exception as exc:
                    failed += 1
                    with UnitOfWork(self.db):
                        export.status = "failed"
                        export.error_message = getattr(exc, "message", str(exc))
                    job_service.log(
                        job_id,
                        "error",
                        "export_segment",
                        getattr(exc, "message", str(exc)),
                        {"export_id": export.id, "segment_id": export.segment_id},
                    )
                progress = int((index / len(exports)) * 100)
                job_service.update_progress(job_id, progress, "exporting_segments")
            if failed:
                raise ValidationAppError(
                    message="Some export segments failed.",
                    detail={"completed": completed, "failed": failed},
                    suggested_action="Check ffmpeg logs and retry failed exports.",
                )
            job_service.succeed(
                job_id,
                {"completed": completed, "failed": failed},
            )
        except Exception as exc:
            code = getattr(exc, "error_code", exc.__class__.__name__)
            message = getattr(exc, "message", str(exc))
            job_service.fail(job_id, code, message)
            job_service.log(job_id, "error", "export", message)

    def _require_detection(self, detection_id: int) -> DetectionResult:
        detection = self.detection_repository.get(detection_id)
        if detection is None:
            raise NotFoundError(
                message="Detection result was not found.",
                detail={"detection_id": detection_id},
            )
        return detection

    def _require_segment(self, segment_id: int) -> DetectionSegment:
        segment = self.detection_repository.get_segment(segment_id)
        if segment is not None:
            return segment
        raise NotFoundError(
            message="Detection segment was not found.",
            detail={"segment_id": segment_id},
        )

    def _select_segments(
        self,
        detection_id: int,
        segment_ids: list[int] | None,
    ) -> list[DetectionSegment]:
        segments = self.detection_repository.list_segments(detection_id)
        if segment_ids is None:
            return segments
        wanted = set(segment_ids)
        selected = [segment for segment in segments if segment.id in wanted]
        missing = sorted(wanted - {segment.id for segment in selected})
        if missing:
            raise ValidationAppError(
                message="Some segments do not belong to the detection result.",
                detail={"missing_segment_ids": missing, "detection_id": detection_id},
            )
        return selected

    def _output_path(
        self,
        detection: DetectionResult,
        segment: DetectionSegment,
        mode: str,
    ) -> Path:
        source_stem = self.storage.safe_filename(Path(detection.source_filename).stem)
        start_ms = int(segment.padded_start_sec * 1000)
        end_ms = int(segment.padded_end_sec * 1000)
        filename = (
            f"{source_stem}_scene_{segment.segment_index:03d}_"
            f"{start_ms}_{end_ms}_{mode}.mp4"
        )
        return self.storage.ensure_under_root(
            self.settings.outputs_dir
            / "exports"
            / f"detection_{detection.id}"
            / filename
        )

    def _thumbnail_path(
        self,
        detection: DetectionResult,
        segment: DetectionSegment,
    ) -> Path:
        source_stem = self.storage.safe_filename(Path(detection.source_filename).stem)
        filename = f"{source_stem}_scene_{segment.segment_index:03d}.jpg"
        return self.storage.ensure_under_root(
            self.settings.thumbnails_dir / f"detection_{detection.id}" / filename
        )

    def _preview_path(
        self,
        detection: DetectionResult,
        segment: DetectionSegment,
    ) -> Path:
        source_stem = self.storage.safe_filename(Path(detection.source_filename).stem)
        filename = f"{source_stem}_scene_{segment.segment_index:03d}_preview.mp4"
        return self.storage.ensure_under_root(
            self.settings.previews_dir / f"detection_{detection.id}" / filename
        )

    def _ffmpeg_command(
        self,
        source_path: Path,
        output_path: Path,
        start_sec: float,
        end_sec: float,
        mode: str,
    ) -> list[str]:
        ffmpeg_status = VideoToolsService(self.settings).ffmpeg_status()
        if not ffmpeg_status.resolved_path:
            raise ValidationAppError(
                message="ffmpeg was not found.",
                suggested_action="Install ffmpeg or configure AISD_FFMPEG_PATH.",
            )
        duration = max(0.01, end_sec - start_sec)
        command = [
            ffmpeg_status.resolved_path,
            "-hide_banner",
            "-y",
            "-ss",
            f"{start_sec:.3f}",
            "-i",
            str(source_path),
            "-t",
            f"{duration:.3f}",
        ]
        if mode == "copy":
            command.extend(["-c", "copy", "-avoid_negative_ts", "make_zero"])
        else:
            command.extend(
                [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "160k",
                ]
            )
        command.append(str(output_path))
        return command

    def _thumbnail_command(
        self,
        source_path: Path,
        output_path: Path,
        timestamp_sec: float,
    ) -> list[str]:
        ffmpeg_status = VideoToolsService(self.settings).ffmpeg_status()
        if not ffmpeg_status.resolved_path:
            raise ValidationAppError(
                message="ffmpeg was not found.",
                suggested_action="Install ffmpeg or configure AISD_FFMPEG_PATH.",
            )
        return [
            ffmpeg_status.resolved_path,
            "-hide_banner",
            "-y",
            "-ss",
            f"{max(0.0, timestamp_sec):.3f}",
            "-i",
            str(source_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=min(640\\,iw):-2",
            "-q:v",
            "3",
            str(output_path),
        ]

    def _preview_command(
        self,
        source_path: Path,
        output_path: Path,
        start_sec: float,
        end_sec: float,
    ) -> list[str]:
        ffmpeg_status = VideoToolsService(self.settings).ffmpeg_status()
        if not ffmpeg_status.resolved_path:
            raise ValidationAppError(
                message="ffmpeg was not found.",
                suggested_action="Install ffmpeg or configure AISD_FFMPEG_PATH.",
            )
        duration = max(0.01, end_sec - start_sec)
        return [
            ffmpeg_status.resolved_path,
            "-hide_banner",
            "-y",
            "-ss",
            f"{max(0.0, start_sec):.3f}",
            "-i",
            str(source_path),
            "-t",
            f"{duration:.3f}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "24",
            "-vf",
            "scale=min(960\\,iw):-2",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    def _run_ffmpeg(self, command: list[str]) -> None:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise ValidationAppError(
                message="ffmpeg export failed.",
                detail={
                    "returncode": completed.returncode,
                    "stderr": completed.stderr[-4000:],
                },
                suggested_action="Retry with reencode mode or inspect the source video.",
            )


def run_export_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        ExportService(db, get_settings()).run_export_job(job_id)
    finally:
        db.close()
