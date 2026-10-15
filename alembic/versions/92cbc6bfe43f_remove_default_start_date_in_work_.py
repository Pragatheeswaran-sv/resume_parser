"""remove_default_start_date_in_work_experience

Revision ID: 92cbc6bfe43f
Revises: 836e5db66f70
Create Date: 2026-10-15 13:57:47.037708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92cbc6bfe43f'
down_revision: Union[str, Sequence[str], None] = '836e5db66f70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: ensure work_experience start_date and end_date are nullable with no default."""
    op.alter_column(
        "work_experience",
        "start_date",
        existing_type=sa.Date(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "work_experience",
        "end_date",
        existing_type=sa.Date(),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "work_experience",
        "start_date",
        existing_type=sa.Date(),
        nullable=True,
    )
