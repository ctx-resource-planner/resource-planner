"""Initial migration (baseline)

Revision ID: 9bb7301202a7
Revises: 
Create Date: 2025-07-25 05:31:19.188747

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9bb7301202a7'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Drop the view first
    op.execute('DROP VIEW IF EXISTS dashboard_utilization_data CASCADE')
    
    # First, change notes to TEXT to avoid truncation
    with op.batch_alter_table('timesheet_uploads', schema=None) as batch_op:
        batch_op.alter_column('notes',
               existing_type=sa.TEXT(),
               type_=sa.Text(),  # Using Text() for unlimited length
               existing_nullable=True)
    
    # Then alter the other columns
    with op.batch_alter_table('timesheet_uploads', schema=None) as batch_op:
        batch_op.alter_column('client_name',
               existing_type=sa.TEXT(),
               type_=sa.String(length=200),
               existing_nullable=True)
        batch_op.alter_column('project_name',
               existing_type=sa.TEXT(),
               type_=sa.String(length=200),
               existing_nullable=True)
        batch_op.alter_column('description',
               existing_type=sa.TEXT(),
               type_=sa.String(length=255),
               existing_nullable=True)
        batch_op.alter_column('service_item',
               existing_type=sa.TEXT(),
               type_=sa.String(length=100),
               existing_nullable=True)
        batch_op.alter_column('comments',
               existing_type=sa.TEXT(),
               type_=sa.String(length=255),
               existing_nullable=True)

    # Recreate the view with the updated column types - FIXED the extra parenthesis
    op.execute('''
    CREATE OR REPLACE VIEW dashboard_utilization_data AS
    SELECT 
        tu.username,
        concat(tu.first_name, ' ', tu.last_name) AS employee_name,
        tu.local_date,
        tu.hours,
        tu.is_billable,
        tu.project_name,
        COALESCE(p.service_line, 'Unknown'::character varying) AS service_line,
        COALESCE(e.service_line, 'Unknown'::character varying) AS employee_service_line,
        COALESCE(e.reporting_manager, 'Unknown'::character varying) AS reporting_manager,
        e.doj,
        e.doe,
        e.designation,
        e.location
    FROM 
        timesheet_uploads tu
        LEFT JOIN projects p ON (tu.project_name = (p.project_name)::text)
        LEFT JOIN employees e ON ((tu.username)::text = (e.email)::text)
    ''')

def downgrade():
    # Drop the view first
    op.execute('DROP VIEW IF EXISTS dashboard_utilization_data CASCADE')
    
    # Revert column types
    with op.batch_alter_table('timesheet_uploads', schema=None) as batch_op:
        batch_op.alter_column('comments',
               existing_type=sa.String(length=255),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('service_item',
               existing_type=sa.String(length=100),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('description',
               existing_type=sa.String(length=255),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('project_name',
               existing_type=sa.String(length=200),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('client_name',
               existing_type=sa.String(length=200),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('notes',
               existing_type=sa.Text(),  # Keep as TEXT in downgrade
               type_=sa.TEXT(),
               existing_nullable=True)
    
    # Recreate the view with original column types - FIXED the extra parenthesis
    op.execute('''
    CREATE OR REPLACE VIEW dashboard_utilization_data AS
    SELECT 
        tu.username,
        concat(tu.first_name, ' ', tu.last_name) AS employee_name,
        tu.local_date,
        tu.hours,
        tu.is_billable,
        tu.project_name,
        COALESCE(p.service_line, 'Unknown'::character varying) AS service_line,
        COALESCE(e.service_line, 'Unknown'::character varying) AS employee_service_line,
        COALESCE(e.reporting_manager, 'Unknown'::character varying) AS reporting_manager,
        e.doj,
        e.doe,
        e.designation,
        e.location
    FROM 
        timesheet_uploads tu
        LEFT JOIN projects p ON (tu.project_name = (p.project_name)::text)
        LEFT JOIN employees e ON ((tu.username)::text = (e.email)::text)
    ''')