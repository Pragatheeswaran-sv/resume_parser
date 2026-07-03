"""index creation for model_config

Revision ID: 45def01a0b2c
Revises: c96238d8f405
Create Date: 2026-07-03 12:00:15.133118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45def01a0b2c'
down_revision: Union[str, Sequence[str], None] = 'c96238d8f405'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_index(
        "ix_ai_model_configs_admin_priority",
        "ai_model_configs",
        ["admin_id", "prioprity_queue"],
    )
def downgrade():
    op.drop_index(
        "ix_ai_model_configs_admin_priority",
        table_name="ai_model_configs",
    )
