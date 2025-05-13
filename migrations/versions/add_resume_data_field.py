"""add resume_data field

Revision ID: add_resume_data_field
Revises: add_keyword_tables
Create Date: 2024-03-21 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_resume_data_field'
down_revision = 'add_keyword_tables'
branch_labels = None
depends_on = None

def upgrade():
    # Поле resume_data уже существует, ничего не делаем
    pass

def downgrade():
    # Удаляем поле resume_data из таблицы candidates (если нужно откатить)
    op.drop_column('candidates', 'resume_data') 