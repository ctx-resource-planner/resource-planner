"""Create business_units table

Revision ID: 430be31a555f
Revises: db330609280e
Create Date: 2025-07-26 02:11:55.169132

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '430be31a555f'
down_revision = 'db330609280e'
branch_labels = None
depends_on = None


def upgrade():
    # Create only the business_units table
    op.create_table('business_units',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('short_name', sa.String(length=20), nullable=False),
        sa.Column('practice_manager', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('short_name')
    )


def downgrade():
    # Only drop the business_units table
    op.drop_table('business_units')