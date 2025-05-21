"""merge heads

Revision ID: 14e14a8b5f58
Revises: 06f41e09e28a, add_rejection_reasons
Create Date: 2025-05-16 16:08:17.643888

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '14e14a8b5f58'
down_revision = ('06f41e09e28a', 'add_rejection_reasons')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
