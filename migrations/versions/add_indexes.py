"""add indexes

Revision ID: add_indexes
Revises: previous_revision
Create Date: 2024-05-13 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_indexes'
down_revision = '0f6491a6b045'
branch_labels = None
depends_on = None

def upgrade():
    # Индексы для таблицы candidates
    op.create_index('ix_candidates_vacancy_id', 'candidates', ['vacancy_id'])
    op.create_index('ix_candidates_id_c_candidate_status', 'candidates', ['id_c_candidate_status'])
    op.create_index('ix_candidates_created_at', 'candidates', ['created_at'])
    op.create_index('ix_candidates_tracking_code', 'candidates', ['tracking_code'])
    
    # Индексы для таблицы vacancies
    op.create_index('ix_vacancies_is_active', 'vacancies', ['is_active'])
    op.create_index('ix_vacancies_status', 'vacancies', ['status'])
    
    # Индексы для таблицы users
    op.create_index('ix_users_role', 'users', ['role'])
    op.create_index('ix_users_is_active', 'users', ['is_active'])

def downgrade():
    # Удаляем индексы
    op.drop_index('ix_candidates_vacancy_id')
    op.drop_index('ix_candidates_id_c_candidate_status')
    op.drop_index('ix_candidates_created_at')
    op.drop_index('ix_candidates_tracking_code')
    op.drop_index('ix_vacancies_is_active')
    op.drop_index('ix_vacancies_status')
    op.drop_index('ix_users_role')
    op.drop_index('ix_users_is_active') 