"""column_for_share_resume_re_try

Revision ID: 836e5db66f70
Revises: f9e8d7c6b5a4
Create Date: 2026-07-09 13:33:14.233099

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '836e5db66f70'
down_revision: Union[str, Sequence[str], None] = 'f9e8d7c6b5a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

