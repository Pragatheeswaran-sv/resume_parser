"""modified share_email_logs table

Revision ID: 72ba7423be23
Revises: d84b98443144
Create Date: 2026-05-11 15:03:05.992492

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '72ba7423be23'
down_revision: Union[str, Sequence[str], None] = 'd84b98443144'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.rename_table("email_share_logs", "email_notification")

    # Drop unwanted columns
    op.drop_constraint(
        "email_share_logs_candidate_id_fkey",
        "email_notification",
        type_="foreignkey"
    )

    op.drop_column("email_notification", "candidate_id")

    # Rename columns
    op.alter_column(
        "email_notification",
        "create_by",
        new_column_name="created_by"
    )

    # Add new columns
    op.add_column(
        "email_notification",
        sa.Column("subject", sa.String(length=500), nullable=True)
    )

    op.add_column(
        "email_notification",
        sa.Column("mail_body", sa.Text(), nullable=True)
    )

    # Step 2: update existing rows
    # op.execute("""
    #     UPDATE email_notification
    #     SET mail_body = ''
    #     WHERE mail_body IS NULL
    # """)

    # # Step 3: make NOT NULL
    # op.alter_column(
    #     "email_notification",
    #     "mail_body",
    #     existing_type=sa.Text(),
    #     nullable=False
    # )

    op.add_column(
        "email_notification",
        sa.Column("status", sa.String(), nullable=True)
    )

    op.add_column(
        "email_notification",
        sa.Column("sent_at", sa.DateTime(), nullable=True)
    )

    op.alter_column(
        "email_notification",
        "cc_address",
        existing_type=sa.String(length=255),
        nullable=True
    )

    # op.alter_column(
    #     "email_notification",
    #     "mail_body",
    #     existing_type=sa.Text(),
    #     nullable=True
    # )

def downgrade() -> None:
    """Downgrade schema."""

    # Rename table back
    op.rename_table("email_notification", "email_share_logs")

    # Remove newly added columns
    op.drop_column("email_share_logs", "sent_at")
    op.drop_column("email_share_logs", "status")
    op.drop_column("email_share_logs", "mail_body")
    op.drop_column("email_share_logs", "subject")

    # Rename column back
    op.alter_column(
        "email_share_logs",
        "created_by",
        new_column_name="create_by"
    )

    # Make cc_address non-nullable again
    op.alter_column(
        "email_share_logs",
        "cc_address",
        existing_type=sa.String(length=255),
        nullable=False
    )

    # Re-add candidate_id column
    op.add_column(
        "email_share_logs",
        sa.Column("candidate_id", sa.UUID(), nullable=False)
    )

    # Recreate foreign key
    op.create_foreign_key(
        "email_share_logs_candidate_id_fkey",
        "email_share_logs",
        "candidates",
        ["candidate_id"],
        ["candidate_id"]
    )