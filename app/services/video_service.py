import hashlib
import json
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.core.video.metadata import VideoMetadata
from app.core.video.probe import FFprobeVideoProbe
from app.core.video.reader import OpenCVVideoReader
from app.db.unit_of_work import UnitOfWork
from app.models.training_video import TrainingVideo
from app.repositories.training_video_repository import TrainingVideoRepository
from app.services.storage_service import StorageService


class VideoService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.storage = StorageService(settings)
        self.repository = TrainingVideoRepository(db)
        self.probe = FFprobeVideoProbe(settings)

    async def register_training_video(
        self,
        upload: UploadFile,
        label_type: str,
    ) -> TrainingVideo:
        if label_type not in {"positive", "negative"}:
            raise ValidationAppError(
                message="label_type must be positive or negative.",
                detail={"label_type": label_type},
                suggested_action="Use label_type=positive or label_type=negative.",
            )
        if not upload.filename:
            raise ValidationAppError(
                message="Upload filename is required.",
                suggested_action="Upload a video file with a valid file name.",
            )

        extension = self.storage.validate_video_extension(upload.filename)
        destination = self.storage.upload_path(upload.filename)
        file_size, sha256 = await self._save_upload(upload, destination)
        try:
            metadata = self._probe_with_opencv_aux(destination)

            video = TrainingVideo(
                label_type=label_type,
                original_filename=upload.filename,
                stored_filename=destination.name,
                path=str(destination),
                sha256=sha256,
                file_size=file_size,
                extension=extension,
                duration=metadata.duration,
                fps=metadata.fps,
                frame_count=metadata.frame_count,
                width=metadata.width,
                height=metadata.height,
                codec=metadata.codec,
                pixel_format=metadata.pixel_format,
                bitrate=metadata.bitrate,
                rotation=metadata.rotation,
                stream_count=metadata.stream_count,
                has_audio=metadata.has_audio,
                metadata_json=json.dumps(metadata.raw, ensure_ascii=True),
                opencv_metadata_json=json.dumps(metadata.opencv, ensure_ascii=True)
                if metadata.opencv is not None
                else None,
                validation_status="valid",
                validation_error=None,
            )

            with UnitOfWork(self.db):
                self.repository.add(video)
            self.db.refresh(video)
            return video
        except Exception:
            if destination.exists():
                destination.unlink()
            raise

    def list_training_videos(self, limit: int = 50) -> list[TrainingVideo]:
        return self.repository.list_recent(limit)

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

    def _probe_with_opencv_aux(self, path: Path) -> VideoMetadata:
        metadata = self.probe.probe(path)
        opencv_metadata: dict[str, object] | None = None
        try:
            with OpenCVVideoReader(path) as reader:
                opencv_metadata = reader.get_metadata()
        except ValidationAppError as exc:
            opencv_metadata = {"status": "unavailable", "message": exc.message}
        return VideoMetadata(
            duration=metadata.duration,
            fps=metadata.fps,
            frame_count=metadata.frame_count,
            width=metadata.width,
            height=metadata.height,
            codec=metadata.codec,
            pixel_format=metadata.pixel_format,
            bitrate=metadata.bitrate,
            rotation=metadata.rotation,
            stream_count=metadata.stream_count,
            has_audio=metadata.has_audio,
            raw=metadata.raw,
            opencv=opencv_metadata,
        )
