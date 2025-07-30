"""merge multiple heads

Revision ID: c96d84567277
Revises: 12345678, clean_add_project_relationship
Create Date: 2025-07-26 05:48:09.056357

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c96d84567277'
down_revision = ('12345678', 'clean_add_project_relationship')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
