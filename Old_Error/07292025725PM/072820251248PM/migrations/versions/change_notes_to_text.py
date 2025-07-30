"""Change notes column to TEXT in timesheet_uploads

Revision ID: 5fc7f88b18de
Revises: 0617bbe53bb4
Create Date: 2025-07-26 01:08:21.441089

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5fc7f88b18de'
down_revision = '0617bbe53bb4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('timesheet_uploads', schema=None) as batch_op:
        batch_op.alter_column('notes',
               existing_type=sa.String(length=255),
               type_=sa.Text(),
               existing_nullable=True)


def downgrade():
    with op.batch_alter_table('timesheet_uploads', schema=None) as batch_op:
        batch_op.alter_column('notes',
               existing_type=sa.Text(),
               type_=sa.String(length=255),
               existing_nullable=True)