from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Feature(Base, TimestampMixin):
    __tablename__ = "features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_video_id: Mapped[int] = mapped_column(
        ForeignKey("training_videos.id"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    dtype: Mapped[str] = mapped_column(String(32), nullable=False)
    shape_json: Mapped[str] = mapped_column(Text, nullable=False)
    frame_interval_sec: Mapped[float] = mapped_column(Float, nullable=False)
    extractor_json: Mapped[str] = mapped_column(Text, nullable=False)
    cache_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    frame_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id"),
        nullable=True,
        index=True,
    )
