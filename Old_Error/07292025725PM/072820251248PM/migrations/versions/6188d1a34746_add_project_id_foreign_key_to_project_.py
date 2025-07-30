# In a new migration file, e.g., 12345678_add_project_relationship.py
"""Add project relationship to project_setups

Revision ID: 12345678
Revises: 74da289076d8
Create Date: 2025-07-26 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '12345678'
down_revision = '74da289076d8'
branch_labels = None
depends_on = None

def upgrade():
    # Only add the project_id column and its foreign key
    with op.batch_alter_table('project_setups', schema=None) as batch_op:
        batch_op.add_column(sa.Column('project_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_project_setups_project_id',
            'projects', 
            ['project_id'], 
            ['id']
        )

def downgrade():
    with op.batch_alter_table('project_setups', schema=None) as batch_op:
        batch_op.drop_constraint('fk_project_setups_project_id', type_='foreignkey')
        batch_op.drop_column('project_id')