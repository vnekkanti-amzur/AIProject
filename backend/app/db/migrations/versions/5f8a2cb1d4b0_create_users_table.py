"""create users table

Revision ID: 5f8a2cb1d4b0
Revises: c791c4b55b97
Create Date: 2026-05-01 15:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5f8a2cb1d4b0"
down_revision: str | None = "c791c4b55b97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("google_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("google_id"),
        schema="public",
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False, schema="public")


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users", schema="public")
    op.drop_table("users", schema="public")
