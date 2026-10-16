"""Store the service-job access of each cell.

Both columns are written by the offline job `jobs.compute_job_access` and stay
null until it has run for the city, which the application reports as UNKNOWN.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cells", sa.Column("job_places_nearby", sa.Integer(), nullable=True))
    op.add_column("cells", sa.Column("job_access_score", sa.Float(), nullable=True))
    op.create_check_constraint(
        op.f("ck_cells_job_access_score_range"), "cells", "job_access_score BETWEEN 0 AND 1"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_cells_job_access_score_range"), "cells", type_="check")
    op.drop_column("cells", "job_access_score")
    op.drop_column("cells", "job_places_nearby")
