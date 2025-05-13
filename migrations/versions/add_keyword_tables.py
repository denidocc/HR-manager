"""add keyword tables

Revision ID: add_keyword_tables
Revises: 
Create Date: 2024-03-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_keyword_tables'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Создаем таблицу категорий ключевых слов
    op.create_table(
        'keyword_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    
    # Создаем таблицу ключевых слов
    op.create_table(
        'keywords',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('word_ru', sa.String(length=100), nullable=True),
        sa.Column('word_en', sa.String(length=100), nullable=True),
        sa.Column('word_tm', sa.String(length=100), nullable=True),
        sa.Column('synonyms', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('industry_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('frequency', sa.Integer(), nullable=False, default=0),
        sa.ForeignKeyConstraint(['category_id'], ['keyword_categories.id'], ),
        sa.ForeignKeyConstraint(['industry_id'], ['industries.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Добавляем начальные категории
    op.bulk_insert(
        sa.table('keyword_categories',
            sa.column('name', sa.String),
            sa.column('code', sa.String),
            sa.column('description', sa.Text),
            sa.column('is_active', sa.Boolean)
        ),
        [
            {'name': 'Образование', 'code': 'education', 'description': 'Образовательные учреждения и степени', 'is_active': True},
            {'name': 'Должности', 'code': 'position', 'description': 'Названия должностей', 'is_active': True},
            {'name': 'Технические навыки', 'code': 'technical_skill', 'description': 'Технические навыки и технологии', 'is_active': True},
            {'name': 'Софт-скиллы', 'code': 'soft_skill', 'description': 'Навыки межличностного общения', 'is_active': True},
            {'name': 'Языки', 'code': 'language', 'description': 'Языки программирования и человеческие языки', 'is_active': True}
        ]
    )
    
    # Добавляем начальные ключевые слова
    op.bulk_insert(
        sa.table('keywords',
            sa.column('category_id', sa.Integer),
            sa.column('word_ru', sa.String),
            sa.column('word_en', sa.String),
            sa.column('word_tm', sa.String),
            sa.column('synonyms', postgresql.ARRAY(sa.String)),
            sa.column('is_active', sa.Boolean),
            sa.column('frequency', sa.Integer)
        ),
        [
            # Образование
            {'category_id': 1, 'word_ru': 'университет', 'word_en': 'university', 'word_tm': 'universitet', 'synonyms': ['вуз', 'высшее учебное заведение'], 'is_active': True, 'frequency': 0},
            {'category_id': 1, 'word_ru': 'институт', 'word_en': 'institute', 'word_tm': 'institut', 'synonyms': ['высшее учебное заведение'], 'is_active': True, 'frequency': 0},
            {'category_id': 1, 'word_ru': 'академия', 'word_en': 'academy', 'word_tm': 'akademiýa', 'synonyms': [], 'is_active': True, 'frequency': 0},
            {'category_id': 1, 'word_ru': 'колледж', 'word_en': 'college', 'word_tm': 'kolledj', 'synonyms': ['техникум'], 'is_active': True, 'frequency': 0},
            
            # Должности
            {'category_id': 2, 'word_ru': 'менеджер', 'word_en': 'manager', 'word_tm': 'menedžer', 'synonyms': ['руководитель'], 'is_active': True, 'frequency': 0},
            {'category_id': 2, 'word_ru': 'директор', 'word_en': 'director', 'word_tm': 'direktor', 'synonyms': ['руководитель'], 'is_active': True, 'frequency': 0},
            {'category_id': 2, 'word_ru': 'специалист', 'word_en': 'specialist', 'word_tm': 'hünärmen', 'synonyms': ['эксперт'], 'is_active': True, 'frequency': 0},
            {'category_id': 2, 'word_ru': 'инженер', 'word_en': 'engineer', 'word_tm': 'injener', 'synonyms': [], 'is_active': True, 'frequency': 0},
            
            # Технические навыки
            {'category_id': 3, 'word_ru': 'python', 'word_en': 'python', 'word_tm': 'python', 'synonyms': ['питон'], 'is_active': True, 'frequency': 0},
            {'category_id': 3, 'word_ru': 'java', 'word_en': 'java', 'word_tm': 'java', 'synonyms': [], 'is_active': True, 'frequency': 0},
            {'category_id': 3, 'word_ru': 'javascript', 'word_en': 'javascript', 'word_tm': 'javascript', 'synonyms': ['js'], 'is_active': True, 'frequency': 0},
            {'category_id': 3, 'word_ru': 'sql', 'word_en': 'sql', 'word_tm': 'sql', 'synonyms': ['structured query language'], 'is_active': True, 'frequency': 0},
            
            # Софт-скиллы
            {'category_id': 4, 'word_ru': 'коммуникабельность', 'word_en': 'communication', 'word_tm': 'araçlyk', 'synonyms': ['общительность'], 'is_active': True, 'frequency': 0},
            {'category_id': 4, 'word_ru': 'лидерство', 'word_en': 'leadership', 'word_tm': 'ýolbaşçylyk', 'synonyms': ['руководство'], 'is_active': True, 'frequency': 0},
            {'category_id': 4, 'word_ru': 'работа в команде', 'word_en': 'teamwork', 'word_tm': 'topar işi', 'synonyms': ['командная работа'], 'is_active': True, 'frequency': 0},
            {'category_id': 4, 'word_ru': 'управление проектами', 'word_en': 'project management', 'word_tm': 'taslamany dolandyrmak', 'synonyms': ['менеджмент проектов'], 'is_active': True, 'frequency': 0},
            
            # Языки
            {'category_id': 5, 'word_ru': 'английский', 'word_en': 'english', 'word_tm': 'iňlis', 'synonyms': ['английский язык'], 'is_active': True, 'frequency': 0},
            {'category_id': 5, 'word_ru': 'русский', 'word_en': 'russian', 'word_tm': 'rus', 'synonyms': ['русский язык'], 'is_active': True, 'frequency': 0},
            {'category_id': 5, 'word_ru': 'туркменский', 'word_en': 'turkmen', 'word_tm': 'türkmen', 'synonyms': ['туркменский язык'], 'is_active': True, 'frequency': 0}
        ]
    )

def downgrade():
    op.drop_table('keywords')
    op.drop_table('keyword_categories') 