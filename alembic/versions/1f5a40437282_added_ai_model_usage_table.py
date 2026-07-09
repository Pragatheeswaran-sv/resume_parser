"""added ai_model_usage_table

Revision ID: 1f5a40437282
Revises: 17b362334785
Create Date: 2026-07-01 10:36:39.917736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f5a40437282'
down_revision: Union[str, Sequence[str], None] = '17b362334785'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "ai_model_usage",
        sa.Column("usage_id",sa.UUID(), nullable=False),
        sa.Column("ai_model_config_id",sa.UUID(), nullable=False),
        sa.Column("minute_window_start", sa.DateTime(), nullable=True),
        sa.Column("minute_requests", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("minute_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("day_window_start", sa.DateTime(), nullable=True),
        sa.Column("day_requests", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("day_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_requests", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("is_rate_limited", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        sa.Column("retry_after", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_table("ai_model_usage")
