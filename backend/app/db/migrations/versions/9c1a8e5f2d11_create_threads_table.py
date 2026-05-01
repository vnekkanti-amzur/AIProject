"""create threads table

Revision ID: 9c1a8e5f2d11
Revises: 5f8a2cb1d4b0
Create Date: 2026-05-01 17:25:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9c1a8e5f2d11"
down_revision: str | None = "5f8a2cb1d4b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_email", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index("ix_threads_user_email", "threads", ["user_email"], unique=False, schema="public")


def downgrade() -> None:
    op.drop_index("ix_threads_user_email", table_name="threads", schema="public")
    op.drop_table("threads", schema="public")
