from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DetectionFeedback(Base, TimestampMixin):
    __tablename__ = "detection_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    detection_result_id: Mapped[int] = mapped_column(
        ForeignKey("detection_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("detection_segments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    model_version_id: Mapped[int] = mapped_column(
        ForeignKey("model_versions.id"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)
