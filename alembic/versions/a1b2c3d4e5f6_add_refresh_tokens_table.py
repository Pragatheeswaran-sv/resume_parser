"""add refresh_tokens table

Revision ID: a1b2c3d4e5f6
Revises: c78006f1b190
Create Date: 2026-04-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c78006f1b190"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("user_id", sa.String, nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean, default=False),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False)),
        sa.Column("updated_at", sa.DateTime(timezone=False)),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
