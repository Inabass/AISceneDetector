"""add detection segments

Revision ID: 0007_detection_segments
Revises: 0006_detections
Create Date: 2026-07-01 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0007_detection_segments"
down_revision: str | None = "0006_detections"
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
    if not _table_exists("detection_segments"):
        op.create_table(
            "detection_segments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("detection_result_id", sa.Integer(), nullable=False),
            sa.Column("segment_index", sa.Integer(), nullable=False),
            sa.Column("start_sec", sa.Float(), nullable=False),
            sa.Column("end_sec", sa.Float(), nullable=False),
            sa.Column("padded_start_sec", sa.Float(), nullable=False),
            sa.Column("padded_end_sec", sa.Float(), nullable=False),
            sa.Column("duration_sec", sa.Float(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("max_score", sa.Float(), nullable=False),
            sa.Column("average_score", sa.Float(), nullable=False),
            sa.Column("representative_timestamp_sec", sa.Float(), nullable=False),
            sa.Column("start_frame_index", sa.Integer(), nullable=True),
            sa.Column("end_frame_index", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["detection_result_id"],
                ["detection_results.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_detection_segments_id", "detection_segments", ["id"])
    _create_index_if_missing(
        "ix_detection_segments_detection_result_id",
        "detection_segments",
        ["detection_result_id"],
    )
    _create_index_if_missing(
        "ix_detection_segments_status",
        "detection_segments",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_detection_segments_status", table_name="detection_segments")
    op.drop_index(
        "ix_detection_segments_detection_result_id",
        table_name="detection_segments",
    )
    op.drop_index("ix_detection_segments_id", table_name="detection_segments")
    op.drop_table("detection_segments")
