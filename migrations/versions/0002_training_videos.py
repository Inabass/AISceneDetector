"""add training videos

Revision ID: 0002_training_videos
Revises: 0001_initial_foundation
Create Date: 2026-06-30 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_training_videos"
down_revision: str | None = "0001_initial_foundation"
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
    if not _table_exists("training_videos"):
        op.create_table(
            "training_videos",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("label_type", sa.String(length=16), nullable=False),
            sa.Column("original_filename", sa.String(length=512), nullable=False),
            sa.Column("stored_filename", sa.String(length=512), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("extension", sa.String(length=16), nullable=False),
            sa.Column("duration", sa.Float(), nullable=True),
            sa.Column("fps", sa.Float(), nullable=True),
            sa.Column("frame_count", sa.Integer(), nullable=True),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("codec", sa.String(length=128), nullable=True),
            sa.Column("pixel_format", sa.String(length=128), nullable=True),
            sa.Column("bitrate", sa.Integer(), nullable=True),
            sa.Column("rotation", sa.Integer(), nullable=True),
            sa.Column("stream_count", sa.Integer(), nullable=True),
            sa.Column("has_audio", sa.Boolean(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("opencv_metadata_json", sa.Text(), nullable=True),
            sa.Column("validation_status", sa.String(length=32), nullable=False),
            sa.Column("validation_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_training_videos_id", "training_videos", ["id"])
    _create_index_if_missing(
        "ix_training_videos_label_type", "training_videos", ["label_type"]
    )
    _create_index_if_missing("ix_training_videos_sha256", "training_videos", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_training_videos_sha256", table_name="training_videos")
    op.drop_index("ix_training_videos_label_type", table_name="training_videos")
    op.drop_index("ix_training_videos_id", table_name="training_videos")
    op.drop_table("training_videos")
