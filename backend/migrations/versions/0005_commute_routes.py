"""Store one typical journey per area and destination, for the route breakdown.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commute_routes",
        sa.Column("neighbourhood_id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("cell_id", sa.String(length=15), nullable=False),
        sa.Column("departs_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("total_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("legs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "total_minutes >= 0", name=op.f("ck_commute_routes_total_minutes_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["neighbourhood_id"],
            ["neighbourhoods.id"],
            name=op.f("fk_commute_routes_neighbourhood_id_neighbourhoods"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["destination_id"],
            ["destinations.id"],
            name=op.f("fk_commute_routes_destination_id_destinations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cell_id"],
            ["cells.h3_index"],
            name=op.f("fk_commute_routes_cell_id_cells"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "neighbourhood_id", "destination_id", name=op.f("pk_commute_routes")
        ),
    )


def downgrade() -> None:
    op.drop_table("commute_routes")
