"""add export preview assets

Revision ID: 0009_export_preview_assets
Revises: 0008_exports
Create Date: 2026-07-01 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0009_export_preview_assets"
down_revision: str | None = "0008_exports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _column_exists("exports", "thumbnail_path"):
        op.add_column("exports", sa.Column("thumbnail_path", sa.Text(), nullable=True))
    if not _column_exists("exports", "preview_path"):
        op.add_column("exports", sa.Column("preview_path", sa.Text(), nullable=True))
    if not _column_exists("exports", "asset_error_message"):
        op.add_column("exports", sa.Column("asset_error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("exports") as batch_op:
        batch_op.drop_column("asset_error_message")
        batch_op.drop_column("preview_path")
        batch_op.drop_column("thumbnail_path")
