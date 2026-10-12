"""changes_in_work_experience_table

Revision ID: 4f6e784741de
Revises: b1c2d3e4f5a6
Create Date: 2026-06-10 11:01:26.841015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f6e784741de'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column(
        "work_experience",
        "start_date",
        existing_type=sa.Date(),
        nullable=True
    )


def downgrade():
    op.alter_column(
        "work_experience",
        "start_date",
        existing_type=sa.Date(),
        nullable=True
    )
