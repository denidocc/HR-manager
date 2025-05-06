import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class VacancyIndustry(db.Model):
    """Связующая таблица между вакансиями и отраслями"""
    __tablename__ = 'vacancy_industries'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    vacancy_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('vacancies.id'), nullable=False)
    industry_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('industries.id'), nullable=False)
    
    # Отношения
    vacancy = so.relationship('Vacancy', back_populates='industries')
    industry = so.relationship('Industry', back_populates='vacancies')
    
    def __repr__(self):
        return f'<VacancyIndustry vacancy_id={self.vacancy_id} industry_id={self.industry_id}>' 