"""Add business_units table and relationship to ProjectSetup

Revision ID: 63aa523230df
Revises: 9bb7301202a7
Create Date: 2025-07-25 06:52:24.177194

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '63aa523230df'
down_revision = '9bb7301202a7'
branch_labels = None
depends_on = None


def upgrade():
    # Create business_units table
    op.create_table('business_units',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('short_name', sa.String(length=10), nullable=False),
        sa.Column('practice_manager', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='t'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('short_name')
    )
    
    # Add business_unit_id to project_setups
    with op.batch_alter_table('project_setups', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_unit_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_project_setups_business_unit_id', 'business_units', ['business_unit_id'], ['id'])
    
    # Explicitly set notes to TEXT type
    with op.batch_alter_table('timesheet_uploads', schema=None) as batch_op:
        batch_op.alter_column('notes',
               existing_type=sa.Text(),  # Keep as TEXT
               type_=sa.Text(),          # Explicitly set to TEXT
               existing_nullable=True)

def downgrade():
    # Drop the foreign key first
    with op.batch_alter_table('project_setups', schema=None) as batch_op:
        batch_op.drop_constraint('fk_project_setups_business_unit_id', type_='foreignkey')
        batch_op.drop_column('business_unit_id')
    
    # Drop the business_units table
    op.drop_table('business_units')
    
    # In downgrade, we'll keep the column as TEXT
    with op.batch_alter_table('timesheet_uploads', schema=None) as batch_op:
        batch_op.alter_column('notes',
               existing_type=sa.Text(),
               type_=sa.Text(),
               existing_nullable=True)
    # ### end Alembic commands ###
