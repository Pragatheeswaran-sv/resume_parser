"""add candidate table and some colmn

Revision ID: b0383ec2ea9e
Revises: d7ab89bb62d8
Create Date: 2026-03-25 14:00:20.561922

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b0383ec2ea9e'
down_revision: Union[str, Sequence[str], None] = 'd7ab89bb62d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --------------------------------------------------
    # 1) Rename tables first
    # --------------------------------------------------
    op.rename_table("emails", "email_logs")
    op.rename_table("fetched_mails", "email_version")

    # --------------------------------------------------
    # 2) Enable UUID generator
    # --------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --------------------------------------------------
    # 3) EMAIL_LOGS: add new UUID column + audit columns
    # --------------------------------------------------
    op.add_column("email_logs", sa.Column("email_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("email_logs", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("email_logs", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("email_logs", sa.Column("created_by", sa.String(), nullable=True))
    op.add_column("email_logs", sa.Column("updated_by", sa.String(), nullable=True))
    op.add_column("email_logs", sa.Column("is_active", sa.Boolean(), nullable=True))

    # Fill UUIDs for existing rows
    op.execute("""
        UPDATE email_logs
        SET email_id = gen_random_uuid()
        WHERE email_id IS NULL
    """)

    op.alter_column("email_logs", "email_id", nullable=False)

    # IMPORTANT: make email_id unique so FK can reference it
    op.create_unique_constraint("uq_email_logs_email_id", "email_logs", ["email_id"])

    # --------------------------------------------------
    # 4) ATTACHMENTS: add UUID PK + TEMP UUID FK + audit columns
    # --------------------------------------------------
    op.add_column("attachments", sa.Column("attachment_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("attachments", sa.Column("new_email_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("attachments", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("attachments", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("attachments", sa.Column("created_by", sa.String(), nullable=True))
    op.add_column("attachments", sa.Column("updated_by", sa.String(), nullable=True))
    op.add_column("attachments", sa.Column("is_active", sa.Boolean(), nullable=True))

    # Fill attachment UUIDs
    op.execute("""
        UPDATE attachments
        SET attachment_id = gen_random_uuid()
        WHERE attachment_id IS NULL
    """)

    # Map old INTEGER attachments.email_id -> new UUID email_logs.email_id
    op.execute("""
        UPDATE attachments a
        SET new_email_id = e.email_id
        FROM email_logs e
        WHERE a.email_id = e.id
    """)

    op.alter_column("attachments", "attachment_id", nullable=False)

    # --------------------------------------------------
    # 5) EMAIL_VERSION: add UUID PK + audit columns
    # --------------------------------------------------
    op.add_column("email_version", sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("email_version", sa.Column("created_at", sa.DateTime(), nullable=True))
    # op.add_column("email_version", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("email_version", sa.Column("created_by", sa.String(), nullable=True))
    op.add_column("email_version", sa.Column("updated_by", sa.String(), nullable=True))
    op.add_column("email_version", sa.Column("is_active", sa.Boolean(), nullable=True))

    op.execute("""
        UPDATE email_version
        SET version_id = gen_random_uuid()
        WHERE version_id IS NULL
    """)

    op.alter_column("email_version", "version_id", nullable=False)

    # --------------------------------------------------
    # 6) Drop old FK and create new FK
    # --------------------------------------------------
    op.drop_constraint("attachments_email_id_fkey", "attachments", type_="foreignkey")

    op.create_foreign_key(
        "attachments_email_id_fkey",
        "attachments",
        "email_logs",
        ["new_email_id"],
        ["email_id"]
    )

    # --------------------------------------------------
    # 7) Cleanup old columns AFTER mapping
    # --------------------------------------------------
    op.drop_column("attachments", "file_path")
    op.drop_column("attachments", "id")
    op.drop_column("attachments", "email_id")
    op.alter_column("attachments", "new_email_id", new_column_name="email_id")

    op.drop_column("email_logs", "processed")
    # keep old email_logs.id for now if it was PK / existing joins depend on it
    # don't drop it yet unless you are also replacing PK constraint safely

    op.drop_column("email_version", "id")
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('email_version', sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False))
    op.drop_column('email_version', 'is_active')
    op.drop_column('email_version', 'updated_by')
    op.drop_column('email_version', 'created_by')
    op.drop_column('email_version', 'created_at')
    op.drop_column('email_version', 'version_id')
    op.add_column('email_logs', sa.Column('processed', sa.BOOLEAN(), autoincrement=False, nullable=True))
    op.add_column('email_logs', sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False))
    op.drop_column('email_logs', 'is_active')
    op.drop_column('email_logs', 'updated_by')
    op.drop_column('email_logs', 'created_by')
    op.drop_column('email_logs', 'updated_at')
    op.drop_column('email_logs', 'created_at')
    op.drop_column('email_logs', 'email_id')
    op.add_column('attachments', sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False))
    op.add_column('attachments', sa.Column('file_path', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'attachments', type_='foreignkey')
    op.create_foreign_key(op.f('attachments_email_id_fkey'), 'attachments', 'emails', ['email_id'], ['id'])
    op.alter_column('attachments', 'email_id',
               existing_type=sa.UUID(),
               type_=sa.INTEGER(),
               existing_nullable=True)
    op.drop_column('attachments', 'is_active')
    op.drop_column('attachments', 'updated_by')
    op.drop_column('attachments', 'created_by')
    op.drop_column('attachments', 'updated_at')
    op.drop_column('attachments', 'created_at')
    op.drop_column('attachments', 'attachment_id')
    op.create_table('fetched_mails',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('mailbox', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('last_uid', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('fetched_mails_pkey'))
    )
    op.create_table('emails',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('message_id', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('uid', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('subject', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('sender', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('processed', sa.BOOLEAN(), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('emails_pkey'))
    )
    op.create_table('resumes',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('file_name', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('name', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('total_experience', sa.NUMERIC(), autoincrement=False, nullable=True),
    sa.Column('skills', postgresql.ARRAY(sa.TEXT()), autoincrement=False, nullable=True),
    sa.Column('companies', postgresql.ARRAY(sa.TEXT()), autoincrement=False, nullable=True),
    sa.Column('education', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('email_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['email_id'], ['emails.id'], name=op.f('resumes_email_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('resumes_pkey'))
    )
    op.create_index(op.f('ix_resumes_id'), 'resumes', ['id'], unique=False)
    # ### end Alembic commands ###
