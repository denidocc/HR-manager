import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class Keyword(db.Model):
    """Модель для ключевых слов с поддержкой мультиязычности"""
    __tablename__ = 'keywords'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    category_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('keyword_categories.id'), nullable=False)
    word_ru: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)  # Русское слово
    word_en: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)   # Английское слово
    word_tm: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)   # Туркменское слово
    synonyms: so.Mapped[list] = so.mapped_column(sa.JSON, default=lambda: [])  # Синонимы на разных языках
    industry_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('industries.id'), nullable=True)  # Связь с отраслью
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    frequency: so.Mapped[int] = so.mapped_column(sa.Integer, default=0)  # Частота встречаемости в резюме
    
    # Отношения
    category = so.relationship('KeywordCategory', back_populates='keywords')
    industry = so.relationship('Industry', back_populates='keywords')
    
    def __repr__(self):
        return f'<Keyword {self.word_ru}>'
    
    def get_word(self, lang='ru'):
        """Получить слово на нужном языке"""
        if lang == 'ru':
            return self.word_ru
        elif lang == 'en':
            return self.word_en
        elif lang == 'tm':
            return self.word_tm
        return self.word_ru  # По умолчанию возвращаем русское слово 