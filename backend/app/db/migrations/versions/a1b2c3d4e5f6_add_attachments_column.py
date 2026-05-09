"""add attachments column to messages table

Revision ID: a1b2c3d4e5f6
Revises: c791c4b55b97
Create Date: 2026-05-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'a1b2c3d4e5f6'
down_revision = 'c791c4b55b97'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'messages',
        sa.Column('attachments', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('messages', 'attachments')
