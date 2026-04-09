"""add admin features: extraction_config table, auth_mail extensions

Revision ID: c1a2b3d4e5f6
Revises: aeda0174eb0c
Create Date: 2026-04-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'ffa117ac816e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    insp = inspect(conn)
    return any(c["name"] == column for c in insp.get_columns(table))


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    insp = inspect(conn)
    return table in insp.get_table_names()


def upgrade() -> None:
    # ── New columns on auth_mail (skip if create_all already added them) ─
    if not _column_exists("auth_mail", "is_blocked"):
        op.add_column('auth_mail', sa.Column('is_blocked', sa.Boolean(), server_default='false', nullable=True))
    if not _column_exists("auth_mail", "extraction_enabled"):
        op.add_column('auth_mail', sa.Column('extraction_enabled', sa.Boolean(), server_default='true', nullable=True))
    if not _column_exists("auth_mail", "last_extraction_at"):
        op.add_column('auth_mail', sa.Column('last_extraction_at', sa.DateTime(), nullable=True))

    # ── extraction_config table (skip if create_all already made it) ─────
    if not _table_exists("extraction_config"):
        op.create_table(
            'extraction_config',
            sa.Column('config_id', sa.UUID(), nullable=False),
            sa.Column('is_paused', sa.Boolean(), nullable=True),
            sa.Column('interval_minutes', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.PrimaryKeyConstraint('config_id'),
        )


def downgrade() -> None:
    op.drop_table('extraction_config')
    op.drop_column('auth_mail', 'last_extraction_at')
    op.drop_column('auth_mail', 'extraction_enabled')
    op.drop_column('auth_mail', 'is_blocked')
