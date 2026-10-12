"""drop embedding column from resumes

Revision ID: e5f6a7b8c9d0
Revises: a1b2c3d4e5f6
Create Date: 2026-05-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    insp = inspect(conn)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if _column_exists("resumes", "embedding"):
        op.drop_column('resumes', 'embedding')


def downgrade() -> None:
    # Restore the pgvector extension and the embedding column via raw SQL
    # because the pgvector Python package is no longer a project dependency.
    if not _column_exists("resumes", "embedding"):
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("ALTER TABLE resumes ADD COLUMN embedding vector(384)")
