"""Add project relationship to project_setups

Revision ID: clean_add_project_relationship
Revises: 74da289076d8
Create Date: 2025-07-26 05:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'clean_add_project_relationship'
down_revision = '74da289076d8'
branch_labels = None
depends_on = None

def upgrade():
    # Add project_id column
    op.add_column('project_setups', sa.Column('project_id', sa.Integer(), nullable=True))
    
    # Create foreign key with explicit name
    op.create_foreign_key(
        'fk_project_setups_project_id',
        'project_setups',
        'projects',
        ['project_id'],
        ['id'],
        ondelete='SET NULL'
    )

def downgrade():
    # Drop the foreign key first
    op.drop_constraint('fk_project_setups_project_id', 'project_setups', type_='foreignkey')
    
    # Then drop the column
    op.drop_column('project_setups', 'project_id')