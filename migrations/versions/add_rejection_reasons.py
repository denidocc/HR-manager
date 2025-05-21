"""add rejection reasons

Revision ID: add_rejection_reasons
Revises: 
Create Date: 2024-03-21

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_rejection_reasons'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Создаем таблицу причин отклонения
    op.create_table('c_rejection_reason',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, default=False),
        sa.Column('order', sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Добавляем стандартные причины отклонения
    op.execute("""
        INSERT INTO c_rejection_reason (name, description, is_active, is_default, "order") VALUES
        ('Не соответствует требованиям вакансии', 'Кандидат не соответствует основным требованиям вакансии', true, true, 1),
        ('Недостаточный опыт работы', 'Опыт работы кандидата меньше требуемого', true, true, 2),
        ('Не подходит по уровню образования', 'Образование не соответствует требованиям вакансии', true, true, 3),
        ('Не прошел тестовое задание', 'Результаты тестового задания не соответствуют ожиданиям', true, true, 4),
        ('Не прошел собеседование', 'Результаты собеседования не соответствуют ожиданиям', true, true, 5),
        ('Отказался от предложения', 'Кандидат отказался от предложения о работе', true, true, 6),
        ('Другая причина', 'Иная причина отклонения кандидата', true, true, 7)
    """)
    
    # Добавляем поле для связи с причиной отклонения в таблицу кандидатов
    op.add_column('candidates', sa.Column('id_c_rejection_reason', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_candidate_rejection_reason',
        'candidates', 'c_rejection_reason',
        ['id_c_rejection_reason'], ['id']
    )

def downgrade():
    # Удаляем связь и поле из таблицы кандидатов
    op.drop_constraint('fk_candidate_rejection_reason', 'candidates', type_='foreignkey')
    op.drop_column('candidates', 'id_c_rejection_reason')
    
    # Удаляем таблицу причин отклонения
    op.drop_table('c_rejection_reason') 