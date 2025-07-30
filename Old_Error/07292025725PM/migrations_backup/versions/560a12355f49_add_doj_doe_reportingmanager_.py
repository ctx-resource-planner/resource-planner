"""Add DOJ, DOE, ReportingManager, Designation, Location to employees

Revision ID: 560a12355f49
Revises: expandtext0001
Create Date: 2025-07-19 01:04:38.442812

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '560a12355f49'
down_revision = 'expandtext0001'
branch_labels = None
depends_on = None

def upgrade():
    # Add new columns to employees table
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('doj', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('doe', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('reporting_manager', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('designation', sa.String(length=100), nullable=True))

def downgrade():
    # Remove new columns from employees table
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.drop_column('designation')
        batch_op.drop_column('reporting_manager')
        batch_op.drop_column('doe')
        batch_op.drop_column('doj')
        batch_op.drop_column('location')