"""Count model requests per day, to keep inside the free daily allowance.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.CheckConstraint("requests >= 0", name=op.f("ck_ai_usage_requests_non_negative")),
        sa.PrimaryKeyConstraint("day", "model", name=op.f("pk_ai_usage")),
    )


def downgrade() -> None:
    op.drop_table("ai_usage")
