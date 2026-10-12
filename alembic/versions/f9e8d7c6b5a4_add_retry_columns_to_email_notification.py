"""add retry_count and last_retry_at to email_notification

Revision ID: f9e8d7c6b5a4
Revises: 45def01a0b2c
Create Date: 2026-07-09 12:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9e8d7c6b5a4"
down_revision: Union[str, Sequence[str], None] = "45def01a0b2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_notification",
        sa.Column(
            "retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.add_column(
        "email_notification", sa.Column("last_retry_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "email_notification", sa.Column("failed_at", sa.DateTime(), nullable=True)
    )
    op.alter_column(
        'email_notification',
        'sent_at',
        existing_type=sa.DateTime(timezone=False),
        nullable=True
    )


def downgrade() -> None:
    op.drop_column("email_notification", "last_retry_at")
    op.drop_column("email_notification", "retry_count")
    op.drop_column("email_notification", "failed_at")
    op.alter_column(
        'email_notification',
        'sent_at',
        existing_type=sa.DateTime(timezone=False),
        nullable=False
    )