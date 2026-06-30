"""video dedup status and relative paths

Revision ID: 0003_video_dedup_tools_status_paths
Revises: 0002_training_videos
Create Date: 2026-06-30 00:00:00
"""
from collections.abc import Sequence
from pathlib import Path

from alembic import op
import sqlalchemy as sa

from app.core.config import get_settings

revision: str = "0003_video_dedup_tools_status_paths"
down_revision: str | None = "0002_training_videos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("training_videos")
    with op.batch_alter_table("training_videos") as batch:
        if "processing_status" not in columns:
            batch.add_column(
                sa.Column(
                    "processing_status",
                    sa.String(length=64),
                    nullable=False,
                    server_default="READY",
                )
            )
        if "duplicate_of_video_id" not in columns:
            batch.add_column(sa.Column("duplicate_of_video_id", sa.Integer(), nullable=True))

    _convert_absolute_paths_to_relative()


def downgrade() -> None:
    columns = _columns("training_videos")
    with op.batch_alter_table("training_videos") as batch:
        if "duplicate_of_video_id" in columns:
            batch.drop_column("duplicate_of_video_id")
        if "processing_status" in columns:
            batch.drop_column("processing_status")


def _convert_absolute_paths_to_relative() -> None:
    settings = get_settings()
    storage_root = settings.storage_root.resolve()
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, path FROM training_videos")).fetchall()
    for video_id, stored_path in rows:
        if not stored_path:
            continue
        path = Path(stored_path)
        if not path.is_absolute():
            continue
        try:
            resolved = path.resolve()
            relative = resolved.relative_to(storage_root).as_posix()
        except ValueError:
            continue
        connection.execute(
            sa.text("UPDATE training_videos SET path = :path WHERE id = :id"),
            {"path": relative, "id": video_id},
        )
