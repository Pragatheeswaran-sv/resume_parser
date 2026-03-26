"""added candidate and some changes in resume

Revision ID: ee6eabbec140
Revises: b0383ec2ea9e
Create Date: 2026-03-25 15:07:09.448104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ee6eabbec140'
down_revision: Union[str, Sequence[str], None] = 'b0383ec2ea9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --------------------------------------------------
    # 1) Create candidates table
    # --------------------------------------------------
    op.create_table(
        'candidates',
        sa.Column('candidate_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('email_address', sa.String(length=255), nullable=True),
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('total_experience', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('updated_by', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('candidate_id')
    )

    # --------------------------------------------------
    # 2) Fix attachments.email_id FK -> email_logs.email_id
    # --------------------------------------------------
    op.drop_constraint('attachments_email_id_fkey', 'attachments', type_='foreignkey')

    op.create_foreign_key(
        'attachments_email_id_fkey',
        'attachments',
        'email_logs',
        ['email_id'],
        ['email_id']
    )

    # --------------------------------------------------
    # 3) Make attachments.attachment_id the PRIMARY KEY
    # --------------------------------------------------
    op.execute("""
        DO $$
        DECLARE
            pk_name text;
        BEGIN
            SELECT conname INTO pk_name
            FROM pg_constraint
            WHERE conrelid = 'attachments'::regclass
            AND contype = 'p';

            IF pk_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE attachments DROP CONSTRAINT %I', pk_name);
            END IF;
        END
        $$;
        """)

        # Create PK on attachment_id
    op.create_primary_key('attachments_pkey', 'attachments', ['attachment_id'])

        # Drop old id column if it still exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='attachments' AND column_name='id'
            ) THEN
                ALTER TABLE attachments DROP COLUMN id;
            END IF;
        END
        $$;
        """)
    # --------------------------------------------------
    # 4) Modify resumes table
    # --------------------------------------------------
    op.add_column('resumes', sa.Column('resume_id', sa.UUID(), nullable=True))
    op.add_column('resumes', sa.Column('attachment_id', sa.UUID(), nullable=True))
    op.add_column('resumes', sa.Column('candidate_id', sa.UUID(), nullable=True))
    op.add_column('resumes', sa.Column('created_by', sa.String(), nullable=True))
    op.add_column('resumes', sa.Column('updated_by', sa.String(), nullable=True))
    op.add_column('resumes', sa.Column('is_active', sa.Boolean(), nullable=True))

    # Fill resume_id for existing rows
    op.execute("""
        UPDATE resumes
        SET resume_id = gen_random_uuid()
        WHERE resume_id IS NULL
    """)

    op.alter_column('resumes', 'resume_id', nullable=False)

    op.alter_column(
        'resumes', 'created_at',
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        nullable=True,
        existing_server_default=sa.text('now()')
    )

    op.alter_column(
        'resumes', 'updated_at',
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=sa.DateTime(),
        nullable=True,
        existing_server_default=sa.text('now()')
    )

    op.drop_index(op.f('ix_resumes_id'), table_name='resumes')
    op.create_index(op.f('ix_resumes_resume_id'), 'resumes', ['resume_id'], unique=False)

    # Drop old FK to email_logs.id
    op.drop_constraint(op.f('resumes_email_id_fkey'), 'resumes', type_='foreignkey')

    # Create new FKs
    op.create_foreign_key(None, 'resumes', 'attachments', ['attachment_id'], ['attachment_id'])
    op.create_foreign_key(None, 'resumes', 'candidates', ['candidate_id'], ['candidate_id'])

    # Drop old unused columns
    op.drop_column('resumes', 'education')
    op.drop_column('resumes', 'email_id')
    op.drop_column('resumes', 'file_name')
    op.drop_column('resumes', 'id')
    op.drop_column('resumes', 'skills')
    op.drop_column('resumes', 'total_experience')
    op.drop_column('resumes', 'companies')
    op.drop_column('resumes', 'name')

    # --------------------------------------------------
    # 5) Make email_logs.email_id the PRIMARY KEY
    # --------------------------------------------------
    op.execute("""
        DO $$
        DECLARE
            pk_name text;
        BEGIN
            SELECT conname INTO pk_name
            FROM pg_constraint
            WHERE conrelid = 'email_logs'::regclass
            AND contype = 'p';

            IF pk_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE email_logs DROP CONSTRAINT %I', pk_name);
            END IF;
        END
        $$;
        """)

        # Create PK on email_id
    op.create_primary_key('email_logs_pkey', 'email_logs', ['email_id'])

        # Drop old id column if it still exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='email_logs' AND column_name='id'
            ) THEN
                ALTER TABLE email_logs DROP COLUMN id;
            END IF;
        END
        $$;
        """)
    
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('resumes', sa.Column('name', sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column('resumes', sa.Column('companies', postgresql.ARRAY(sa.TEXT()), autoincrement=False, nullable=True))
    op.add_column('resumes', sa.Column('total_experience', sa.NUMERIC(), autoincrement=False, nullable=True))
    op.add_column('resumes', sa.Column('skills', postgresql.ARRAY(sa.TEXT()), autoincrement=False, nullable=True))
    op.add_column('resumes', sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False))
    op.add_column('resumes', sa.Column('file_name', sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column('resumes', sa.Column('email_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('resumes', sa.Column('education', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'resumes', type_='foreignkey')
    op.drop_constraint(None, 'resumes', type_='foreignkey')
    op.create_foreign_key(op.f('resumes_email_id_fkey'), 'resumes', 'email_logs', ['email_id'], ['id'])
    op.drop_index(op.f('ix_resumes_resume_id'), table_name='resumes')
    op.create_index(op.f('ix_resumes_id'), 'resumes', ['id'], unique=False)
    op.alter_column('resumes', 'updated_at',
               existing_type=sa.DateTime(),
               type_=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('resumes', 'created_at',
               existing_type=sa.DateTime(),
               type_=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.drop_column('resumes', 'is_active')
    op.drop_column('resumes', 'updated_by')
    op.drop_column('resumes', 'created_by')
    op.drop_column('resumes', 'candidate_id')
    op.drop_column('resumes', 'attachment_id')
    op.drop_column('resumes', 'resume_id')
    op.add_column('email_logs', sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False))
    op.create_unique_constraint(op.f('uq_email_logs_email_id'), 'email_logs', ['email_id'], postgresql_nulls_not_distinct=False)
    op.drop_table('candidates')
    # ### end Alembic commands ###
