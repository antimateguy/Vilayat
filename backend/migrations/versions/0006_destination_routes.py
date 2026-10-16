"""Store one typical journey between two destinations (campus to employer).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "destination_routes",
        sa.Column("from_destination_id", sa.Integer(), nullable=False),
        sa.Column("to_destination_id", sa.Integer(), nullable=False),
        sa.Column("departs_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("total_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("legs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "total_minutes >= 0", name=op.f("ck_destination_routes_total_minutes_non_negative")
        ),
        sa.CheckConstraint(
            "from_destination_id <> to_destination_id",
            name=op.f("ck_destination_routes_different_destinations"),
        ),
        sa.ForeignKeyConstraint(
            ["from_destination_id"],
            ["destinations.id"],
            name=op.f("fk_destination_routes_from_destination_id_destinations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_destination_id"],
            ["destinations.id"],
            name=op.f("fk_destination_routes_to_destination_id_destinations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "from_destination_id", "to_destination_id", name=op.f("pk_destination_routes")
        ),
    )


def downgrade() -> None:
    op.drop_table("destination_routes")
