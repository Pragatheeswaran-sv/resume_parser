"""add email share tables

Revision ID: a1b2c3d4e5f6
Revises: e0c93e322ea5
Create Date: 2026-04-28 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8276ff4c1c94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_provider_config',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('provider_name', sa.String(50), nullable=False),
        sa.Column('from_email', sa.String(255), nullable=False),
        sa.Column('host', sa.String(255), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('password', sa.String(255), nullable=True),
        sa.Column('tls_enabled', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('active', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'email_templates',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('template_name', sa.String(255), nullable=False, unique=True),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
    )

    # Seed default SMTP config (update credentials before use)
    op.execute("""
        INSERT INTO email_provider_config (provider_name, from_email, host, port, username, password, tls_enabled, active)
        VALUES (
            'SMTP',
            'kesavan.t.mitrahsoft@gmail.com',
            'smtp.gmail.com',
            587,
            'kesavan.t.mitrahsoft@gmail.com',
            'krwf qkiv pedy nsem',
            TRUE,
            TRUE
        )
    """)

    # Seed Resume Template
    op.execute("""
        INSERT INTO email_templates (template_name, subject, body, is_active)
        VALUES (
            'Resume Template',
            'Resume - {{name}}',
            '<html>
<body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
<p>Hello,</p>
<p>Please find below the candidate details:</p>
<div style="padding: 12px 16px; background: #f9f9f9; border-left: 4px solid #2196F3; margin: 16px 0;">
{{candidate_fields}}
</div>
<p>The resume is attached for your reference.</p>
<br>
<p>Regards,<br>Recruitment Team</p>
</body>
</html>',
            TRUE
        )
    """)


def downgrade() -> None:
    op.drop_table('email_templates')
    op.drop_table('email_provider_config')
