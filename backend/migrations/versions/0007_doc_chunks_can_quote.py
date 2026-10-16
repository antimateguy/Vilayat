"""Mark document chunks whose text may not be shown word for word.

Official pages fetched for the Ask library are searched and linked, but their
passages are shown only where the licence allows it (laws, the project's own
notes). Existing chunks are the project's own notes, so they default to true.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "doc_chunks",
        sa.Column("can_quote", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("doc_chunks", "can_quote")
