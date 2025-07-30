"""Add audit fields to ProjectSetup model

Revision ID: 0617bbe53bb4
Revises: 63aa523230df
Create Date: 2025-07-26 00:56:41.157410

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '0617bbe53bb4'
down_revision = '63aa523230df'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns as nullable first
    with op.batch_alter_table('project_setups', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_by', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('updated_by', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    # Set default values for existing rows
    conn = op.get_bind()
    conn.execute(text("""
        UPDATE project_setups 
        SET 
            created_by = 'system',
            updated_by = 'system',
            created_at = NOW(),
            updated_at = NOW()
    """))
    
    # Now make the columns NOT NULL
    with op.batch_alter_table('project_setups', schema=None) as batch_op:
        batch_op.alter_column('created_by', nullable=False)
        batch_op.alter_column('created_at', nullable=False)
        batch_op.alter_column('updated_at', nullable=False)
        batch_op.create_unique_constraint('uq_project_name_quickbooks', ['project_name_quickbooks'])


def downgrade():
    with op.batch_alter_table('project_setups', schema=None) as batch_op:
        batch_op.drop_constraint('uq_project_name_quickbooks', type_='unique')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')
        batch_op.drop_column('updated_by')
        batch_op.drop_column('created_by')