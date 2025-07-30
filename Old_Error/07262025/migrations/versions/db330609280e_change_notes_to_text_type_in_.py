"""Change notes to Text type in TimesheetUpload

Revision ID: db330609280e
Revises: 0a10e81094d7
Create Date: 2025-07-26 02:04:55.713240

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'db330609280e'
down_revision = '0a10e81094d7'
branch_labels = None
depends_on = None


def upgrade():
    # First, create a new text column
    op.add_column('timesheet_uploads', sa.Column('notes_new', sa.Text(), nullable=True))
    
    # Copy data from old column to new column
    op.execute('UPDATE timesheet_uploads SET notes_new = notes')
    
    # Drop the old column
    op.drop_column('timesheet_uploads', 'notes')
    
    # Rename the new column
    op.alter_column('timesheet_uploads', 'notes_new', new_column_name='notes')


def downgrade():
    # First, create a new varchar column
    op.add_column('timesheet_uploads', sa.Column('notes_old', sa.String(length=255), nullable=True))
    
    # Copy data from text column to varchar column (with truncation if needed)
    op.execute('''
        UPDATE timesheet_uploads 
        SET notes_old = 
            CASE 
                WHEN LENGTH(notes) > 255 THEN SUBSTRING(notes, 1, 252) || '...' 
                ELSE notes 
            END
    ''')
    
    # Drop the text column
    op.drop_column('timesheet_uploads', 'notes')
    
    # Rename the varchar column
    op.alter_column('timesheet_uploads', 'notes_old', new_column_name='notes')