from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrainingVideo(Base, TimestampMixin):
    __tablename__ = "training_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    label_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)

    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pixel_format: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rotation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stream_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_audio: Mapped[bool | None] = mapped_column(nullable=True)

    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    opencv_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
