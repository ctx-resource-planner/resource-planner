"""Add business_unit_id to project_setups

Revision ID: 74da289076d8
Revises: 430be31a555f
Create Date: 2025-07-26 02:19:09.506655

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '74da289076d8'
down_revision = '430be31a555f'
branch_labels = None
depends_on = None


def upgrade():
    # Add business_unit_id column and create foreign key
    with op.batch_alter_table('project_setups', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_unit_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_project_setups_business_unit_id',  # Named constraint for better error messages
            'business_units',
            ['business_unit_id'],
            ['id'],
            ondelete='SET NULL'  # Handle case when a business unit is deleted
        )


def downgrade():
    # Remove the foreign key and column
    with op.batch_alter_table('project_setups', schema=None) as batch_op:
        batch_op.drop_constraint('fk_project_setups_business_unit_id', type_='foreignkey')
        batch_op.drop_column('business_unit_id')