"""Add business_units table and relationship to ProjectSetup

Revision ID: 0a10e81094d7
Revises: 5fc7f88b18de
Create Date: 2025-07-26 01:48:29.314072

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0a10e81094d7'
down_revision = '5fc7f88b18de'
branch_labels = None
depends_on = None


def upgrade():
    # Create business_units table
    op.create_table('business_units',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('short_name', sa.String(length=20), nullable=False),
        sa.Column('practice_manager', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('short_name')
    )
    
    # Add business_unit_id to project_setups
    with op.batch_alter_table('project_setups', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_unit_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_project_setups_business_unit_id', 'business_units', ['business_unit_id'], ['id'])
    
    # Handle the notes column with data preservation
    with op.batch_alter_table('timesheet_uploads', schema=None) as batch_op:
        # Create a temporary column to hold the data
        batch_op.add_column(sa.Column('notes_temp', sa.Text(), nullable=True))
        
        # Copy data to temporary column
        op.execute('''
            UPDATE timesheet_uploads 
            SET notes_temp = notes
        ''')
        
        # Drop the original column
        batch_op.drop_column('notes')
        
        # Recreate the column with TEXT type
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
        
        # Copy data back
        op.execute('''
            UPDATE timesheet_uploads 
            SET notes = notes_temp
        ''')
        
        # Drop the temporary column
        batch_op.drop_column('notes_temp')


def downgrade():
    # Handle the notes column in downgrade
    with op.batch_alter_table('timesheet_uploads', schema=None) as batch_op:
        # Similar process to preserve data
        batch_op.add_column(sa.Column('notes_temp', sa.Text(), nullable=True))
        op.execute('UPDATE timesheet_uploads SET notes_temp = notes')
        batch_op.drop_column('notes')
        batch_op.add_column(sa.Column('notes', sa.String(length=255), nullable=True))
        op.execute('''
            UPDATE timesheet_uploads 
            SET notes = 
                CASE 
                    WHEN LENGTH(notes_temp) > 255 
                    THEN SUBSTRING(notes_temp, 1, 252) || '...' 
                    ELSE notes_temp 
                END
        ''')
        batch_op.drop_column('notes_temp')

    # Drop the business_unit foreign key and column
    with op.batch_alter_table('project_setups', schema=None) as batch_op:
        batch_op.drop_constraint('fk_project_setups_business_unit_id', type_='foreignkey')
        batch_op.drop_column('business_unit_id')

    # Drop the business_units table
    op.drop_table('business_units')