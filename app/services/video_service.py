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
        duplicate = self.repository.get_by_sha256(sha256)
        if duplicate is not None:
            if destination.exists():
                destination.unlink()
            setattr(duplicate, "_duplicated_response", True)
            setattr(duplicate, "_duplicate_source_video_id", duplicate.id)
            return duplicate

        try:
            self._validate_content_sniff(destination, extension)
            metadata = self._probe_with_opencv_aux(destination)
            processing_status = "READY"
            validation_error = None
            if metadata.opencv and metadata.opencv.get("status") == "unavailable":
                processing_status = "WARNING_OPENCV_UNREADABLE"
                validation_error = str(metadata.opencv.get("message"))

            video = TrainingVideo(
                label_type=label_type,
                original_filename=upload.filename,
                stored_filename=destination.name,
                path=self.storage.relative_path(destination),
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
                processing_status=processing_status,
                validation_error=validation_error,
                duplicate_of_video_id=None,
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


def _looks_like_known_video_container(head: bytes) -> bool:
    return (
        b"ftyp" in head[:32]
        or head.startswith(b"\x1a\x45\xdf\xa3")
        or (head.startswith(b"RIFF") and b"AVI " in head[:16])
    )


def _looks_like_text(head: bytes) -> bool:
    if not head:
        return False
    sample = head[:128]
    printable = sum(
        byte in b"\r\n\t" or 32 <= byte <= 126
        for byte in sample
    )
    return printable / len(sample) > 0.95
