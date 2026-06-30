"""initial foundation schema

Revision ID: 0001_initial_foundation
Revises:
Create Date: 2026-06-30 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_foundation"
down_revision: str | None = None
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
    if not _table_exists("jobs"):
        op.create_table(
            "jobs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("progress", sa.Integer(), nullable=False),
            sa.Column("current_step", sa.String(length=128), nullable=True),
            sa.Column("params_json", sa.Text(), nullable=True),
            sa.Column("checkpoint_json", sa.Text(), nullable=True),
            sa.Column("error_code", sa.String(length=128), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_jobs_id", "jobs", ["id"])
    _create_index_if_missing("ix_jobs_status", "jobs", ["status"])
    _create_index_if_missing("ix_jobs_type", "jobs", ["type"])

    if not _table_exists("settings"):
        op.create_table(
            "settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(length=128), nullable=False),
            sa.Column("value_json", sa.Text(), nullable=False),
            sa.Column("editable", sa.Boolean(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key"),
        )
    _create_index_if_missing("ix_settings_id", "settings", ["id"])

    if not _table_exists("job_logs"):
        op.create_table(
            "job_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=False),
            sa.Column("level", sa.String(length=16), nullable=False),
            sa.Column("step", sa.String(length=128), nullable=True),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("details_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_job_logs_id", "job_logs", ["id"])
    _create_index_if_missing("ix_job_logs_job_id", "job_logs", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_job_logs_job_id", table_name="job_logs")
    op.drop_index("ix_job_logs_id", table_name="job_logs")
    op.drop_table("job_logs")
    op.drop_index("ix_settings_id", table_name="settings")
    op.drop_table("settings")
    op.drop_index("ix_jobs_type", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_id", table_name="jobs")
    op.drop_table("jobs")
