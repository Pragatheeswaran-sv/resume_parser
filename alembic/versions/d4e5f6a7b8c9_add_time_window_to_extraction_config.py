"""add time window columns to extraction_config

Revision ID: d4e5f6a7b8c9
Revises: ffa117ac816e, c1a2b3d4e5f6
Create Date: 2026-04-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = ("ffa117ac816e", "c1a2b3d4e5f6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    insp = inspect(conn)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists("extraction_config", "window_enabled"):
        op.add_column(
            "extraction_config",
            sa.Column("window_enabled", sa.Boolean(), server_default="false", nullable=True),
        )
    if not _column_exists("extraction_config", "window_start_time"):
        op.add_column(
            "extraction_config",
            sa.Column("window_start_time", sa.String(5), nullable=True),
        )
    if not _column_exists("extraction_config", "window_end_time"):
        op.add_column(
            "extraction_config",
            sa.Column("window_end_time", sa.String(5), nullable=True),
        )
    if not _column_exists("extraction_config", "window_timezone"):
        op.add_column(
            "extraction_config",
            sa.Column(
                "window_timezone",
                sa.String(50),
                server_default="Asia/Kolkata",
                nullable=True,
            ),
        )


def downgrade() -> None:
    op.drop_column("extraction_config", "window_timezone")
    op.drop_column("extraction_config", "window_end_time")
    op.drop_column("extraction_config", "window_start_time")
    op.drop_column("extraction_config", "window_enabled")
