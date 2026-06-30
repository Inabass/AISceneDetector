"""add feature metadata

Revision ID: 0004_features
Revises: 0003_video_dedup_tools_status_paths
Create Date: 2026-06-30 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_features"
down_revision: str | None = "0003_video_dedup_tools_status_paths"
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
    if not _table_exists("features"):
        op.create_table(
            "features",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source_video_id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=64), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column("dtype", sa.String(length=32), nullable=False),
            sa.Column("shape_json", sa.Text(), nullable=False),
            sa.Column("frame_interval_sec", sa.Float(), nullable=False),
            sa.Column("extractor_json", sa.Text(), nullable=False),
            sa.Column("cache_key", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("frame_count", sa.Integer(), nullable=False),
            sa.Column("created_by_job_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by_job_id"], ["jobs.id"]),
            sa.ForeignKeyConstraint(["source_video_id"], ["training_videos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_features_id", "features", ["id"])
    _create_index_if_missing("ix_features_source_video_id", "features", ["source_video_id"])
    _create_index_if_missing("ix_features_kind", "features", ["kind"])
    _create_index_if_missing("ix_features_cache_key", "features", ["cache_key"])
    _create_index_if_missing("ix_features_status", "features", ["status"])
    _create_index_if_missing("ix_features_created_by_job_id", "features", ["created_by_job_id"])


def downgrade() -> None:
    op.drop_index("ix_features_created_by_job_id", table_name="features")
    op.drop_index("ix_features_status", table_name="features")
    op.drop_index("ix_features_cache_key", table_name="features")
    op.drop_index("ix_features_kind", table_name="features")
    op.drop_index("ix_features_source_video_id", table_name="features")
    op.drop_index("ix_features_id", table_name="features")
    op.drop_table("features")
