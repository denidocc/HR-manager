import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class KeywordCategory(db.Model):
    """Модель для категорий ключевых слов (образование, должности, навыки и т.д.)"""
    __tablename__ = 'keyword_categories'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    code: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False, unique=True)  # education, position, skill, etc.
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    # Отношения
    keywords = so.relationship('Keyword', back_populates='category', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<KeywordCategory {self.name}>' 