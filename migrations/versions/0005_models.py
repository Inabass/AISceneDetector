"""add model registry

Revision ID: 0005_models
Revises: 0004_features
Create Date: 2026-07-01 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_models"
down_revision: str | None = "0004_features"
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


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
    unique: bool = False,
) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    if not _table_exists("ai_models"):
        op.create_table(
            "ai_models",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("active_version_id", sa.Integer(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["active_version_id"], ["model_versions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _table_exists("model_versions"):
        op.create_table(
            "model_versions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("model_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.String(length=32), nullable=False),
            sa.Column("parent_version_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("artifact_path", sa.Text(), nullable=False),
            sa.Column("feature_set_path", sa.Text(), nullable=False),
            sa.Column("thresholds_json", sa.Text(), nullable=False),
            sa.Column("metrics_json", sa.Text(), nullable=False),
            sa.Column("extractor_json", sa.Text(), nullable=False),
            sa.Column("matcher_json", sa.Text(), nullable=False),
            sa.Column("cluster_json", sa.Text(), nullable=False),
            sa.Column("classifier_json", sa.Text(), nullable=False),
            sa.Column("created_by_job_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by_job_id"], ["jobs.id"]),
            sa.ForeignKeyConstraint(["model_id"], ["ai_models.id"]),
            sa.ForeignKeyConstraint(["parent_version_id"], ["model_versions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("model_id", "version", name="uq_model_versions_model_version"),
        )

    _create_index_if_missing("ix_ai_models_id", "ai_models", ["id"])
    _create_index_if_missing("ix_ai_models_name", "ai_models", ["name"])
    _create_index_if_missing(
        "ix_ai_models_active_version_id",
        "ai_models",
        ["active_version_id"],
    )
    _create_index_if_missing("ix_model_versions_id", "model_versions", ["id"])
    _create_index_if_missing("ix_model_versions_model_id", "model_versions", ["model_id"])
    _create_index_if_missing(
        "ix_model_versions_parent_version_id",
        "model_versions",
        ["parent_version_id"],
    )
    _create_index_if_missing("ix_model_versions_status", "model_versions", ["status"])
    _create_index_if_missing(
        "ix_model_versions_created_by_job_id",
        "model_versions",
        ["created_by_job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_model_versions_created_by_job_id", table_name="model_versions")
    op.drop_index("ix_model_versions_status", table_name="model_versions")
    op.drop_index("ix_model_versions_parent_version_id", table_name="model_versions")
    op.drop_index("ix_model_versions_model_id", table_name="model_versions")
    op.drop_index("ix_model_versions_id", table_name="model_versions")
    op.drop_index("ix_ai_models_active_version_id", table_name="ai_models")
    op.drop_index("ix_ai_models_name", table_name="ai_models")
    op.drop_index("ix_ai_models_id", table_name="ai_models")
    op.drop_table("model_versions")
    op.drop_table("ai_models")
