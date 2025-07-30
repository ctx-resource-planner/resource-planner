from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'expandtext0001'
down_revision = 'c090bf08f66c'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('timesheet_uploads', 'notes', type_=sa.Text())
    op.alter_column('timesheet_uploads', 'description', type_=sa.Text())
    op.alter_column('timesheet_uploads', 'client_name', type_=sa.Text())
    op.alter_column('timesheet_uploads', 'project_name', type_=sa.Text())
    op.alter_column('timesheet_uploads', 'service_item', type_=sa.Text())
    op.alter_column('timesheet_uploads', 'comments', type_=sa.Text())

def downgrade():
    op.alter_column('timesheet_uploads', 'notes', type_=sa.String(length=255))
    op.alter_column('timesheet_uploads', 'description', type_=sa.String(length=255))
    op.alter_column('timesheet_uploads', 'client_name', type_=sa.String(length=200))
    op.alter_column('timesheet_uploads', 'project_name', type_=sa.String(length=200))
    op.alter_column('timesheet_uploads', 'service_item', type_=sa.String(length=100))
    op.alter_column('timesheet_uploads', 'comments', type_=sa.String(length=255))
    
    # ### end Alembic commands ###
