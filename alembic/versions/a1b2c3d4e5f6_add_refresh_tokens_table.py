"""obsolete duplicate refresh_tokens migration

Revision ID: 6f3a2b1c9d8e
Revises: c78006f1b190
Create Date: 2026-04-13 00:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "6f3a2b1c9d8e"
down_revision: Union[str, Sequence[str], None] = "c78006f1b190"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep the old duplicate revision in the graph without applying changes."""
    pass


def downgrade() -> None:
    """No-op because this migration no longer owns any schema changes."""
    pass
