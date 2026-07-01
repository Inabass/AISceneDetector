"""add detection results

Revision ID: 0006_detections
Revises: 0005_models
Create Date: 2026-07-01 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_detections"
down_revision: str | None = "0005_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    if not _table_exists("detection_results"):
        op.create_table(
            "detection_results",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source_video_path", sa.Text(), nullable=False),
            sa.Column("source_filename", sa.String(length=512), nullable=False),
            sa.Column("source_sha256", sa.String(length=64), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("duration", sa.Float(), nullable=True),
            sa.Column("fps", sa.Float(), nullable=True),
            sa.Column("frame_count", sa.Integer(), nullable=True),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("model_version_id", sa.Integer(), nullable=False),
            sa.Column("settings_json", sa.Text(), nullable=False),
            sa.Column("timeline_path", sa.Text(), nullable=True),
            sa.Column("summary_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
            sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_detection_results_id", "detection_results", ["id"])
    _create_index_if_missing(
        "ix_detection_results_source_sha256",
        "detection_results",
        ["source_sha256"],
    )
    _create_index_if_missing(
        "ix_detection_results_model_version_id",
        "detection_results",
        ["model_version_id"],
    )
    _create_index_if_missing(
        "ix_detection_results_status",
        "detection_results",
        ["status"],
    )
    _create_index_if_missing("ix_detection_results_job_id", "detection_results", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_detection_results_job_id", table_name="detection_results")
    op.drop_index("ix_detection_results_status", table_name="detection_results")
    op.drop_index("ix_detection_results_model_version_id", table_name="detection_results")
    op.drop_index("ix_detection_results_source_sha256", table_name="detection_results")
    op.drop_index("ix_detection_results_id", table_name="detection_results")
    op.drop_table("detection_results")
