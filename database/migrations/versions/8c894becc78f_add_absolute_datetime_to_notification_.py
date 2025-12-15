"""Add absolute_datetime to notification templates

Revision ID: 8c894becc78f
Revises: 303f89838887
Create Date: 2025-12-13 18:11:31.591514

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c894becc78f'
down_revision = '303f89838887'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite не поддерживает ALTER COLUMN напрямую, используем batch_alter_table
    with op.batch_alter_table('notification_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('absolute_datetime', sa.DateTime(), nullable=True))
        batch_op.alter_column('time_before_event',
                   existing_type=sa.INTEGER(),
                   nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('notification_templates', schema=None) as batch_op:
        batch_op.alter_column('time_before_event',
                   existing_type=sa.INTEGER(),
                   nullable=False)
        batch_op.drop_column('absolute_datetime')

