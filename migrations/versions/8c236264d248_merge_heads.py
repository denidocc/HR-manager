"""merge heads

Revision ID: 8c236264d248
Revises: 41945220a023, add_resume_data_field
Create Date: 2025-05-12 16:45:05.330448

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c236264d248'
down_revision = ('41945220a023', 'add_resume_data_field')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
