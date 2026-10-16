"""Store travel times from one destination to another.

The full-day loop is home, campus, job, home. Its middle leg, campus to job,
runs between two destinations, which the cell-based travel_times table cannot
hold. This table holds it, filled by the same offline routing job.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "destination_travel_times",
        sa.Column("from_destination_id", sa.Integer(), nullable=False),
        sa.Column("to_destination_id", sa.Integer(), nullable=False),
        sa.Column("time_window", sa.String(length=32), nullable=False),
        sa.Column("minutes", sa.SmallInteger(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "time_window IN ('weekday_morning', 'weekday_evening')",
            name=op.f("ck_destination_travel_times_time_window"),
        ),
        sa.CheckConstraint(
            "minutes >= 0", name=op.f("ck_destination_travel_times_minutes_non_negative")
        ),
        sa.CheckConstraint(
            "from_destination_id <> to_destination_id",
            name=op.f("ck_destination_travel_times_different_destinations"),
        ),
        sa.ForeignKeyConstraint(
            ["from_destination_id"],
            ["destinations.id"],
            name=op.f("fk_destination_travel_times_from_destination_id_destinations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_destination_id"],
            ["destinations.id"],
            name=op.f("fk_destination_travel_times_to_destination_id_destinations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "from_destination_id",
            "to_destination_id",
            "time_window",
            name=op.f("pk_destination_travel_times"),
        ),
    )
    op.create_index(
        op.f("ix_destination_travel_times_to_destination_id"),
        "destination_travel_times",
        ["to_destination_id"],
    )


def downgrade() -> None:
    op.drop_table("destination_travel_times")
