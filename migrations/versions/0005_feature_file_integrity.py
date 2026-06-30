"""Add feature file integrity metadata.

Revision ID: 0005_feature_file_integrity
Revises: 0004_features
Create Date: 2026-06-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_feature_file_integrity"
down_revision: str | None = "0004_features"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("features", sa.Column("file_sha256", sa.String(length=64), nullable=True))
    op.add_column("features", sa.Column("file_size", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("features", "file_size")
    op.drop_column("features", "file_sha256")
