"""add email_from_sender flag to candidates

Revision ID: a7a9d1b2c3f4
Revises: ee6eabbec140
Create Date: 2026-03-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7a9d1b2c3f4'
down_revision: Union[str, Sequence[str], None] = 'ee6eabbec140'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'candidates',
        sa.Column(
            'email_from_sender',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false')
        )
    )


def downgrade() -> None:
    op.drop_column('candidates', 'email_from_sender')
