"""add exports

Revision ID: 0008_exports
Revises: 0007_detection_segments
Create Date: 2026-07-01 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_exports"
down_revision: str | None = "0007_detection_segments"
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
    if not _table_exists("exports"):
        op.create_table(
            "exports",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("detection_result_id", sa.Integer(), nullable=False),
            sa.Column("segment_id", sa.Integer(), nullable=True),
            sa.Column("mode", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("output_path", sa.Text(), nullable=True),
            sa.Column("ffmpeg_args_json", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("job_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["detection_result_id"], ["detection_results.id"]),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
            sa.ForeignKeyConstraint(["segment_id"], ["detection_segments.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_exports_id", "exports", ["id"])
    _create_index_if_missing("ix_exports_detection_result_id", "exports", ["detection_result_id"])
    _create_index_if_missing("ix_exports_segment_id", "exports", ["segment_id"])
    _create_index_if_missing("ix_exports_status", "exports", ["status"])
    _create_index_if_missing("ix_exports_job_id", "exports", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_exports_job_id", table_name="exports")
    op.drop_index("ix_exports_status", table_name="exports")
    op.drop_index("ix_exports_segment_id", table_name="exports")
    op.drop_index("ix_exports_detection_result_id", table_name="exports")
    op.drop_index("ix_exports_id", table_name="exports")
    op.drop_table("exports")
