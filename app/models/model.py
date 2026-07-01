from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AiModel(Base, TimestampMixin):
    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_version_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("ai_models.id"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_versions.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    feature_set_path: Mapped[str] = mapped_column(Text, nullable=False)
    thresholds_json: Mapped[str] = mapped_column(Text, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    extractor_json: Mapped[str] = mapped_column(Text, nullable=False)
    matcher_json: Mapped[str] = mapped_column(Text, nullable=False)
    cluster_json: Mapped[str] = mapped_column(Text, nullable=False)
    classifier_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id"),
        nullable=True,
        index=True,
    )
