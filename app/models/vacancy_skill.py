import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class VacancySkill(db.Model):
    """Связующая таблица между вакансиями и навыками"""
    __tablename__ = 'vacancy_skills'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    vacancy_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('vacancies.id'), nullable=False)
    skill_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('skills.id'), nullable=False)
    is_required: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)  # Обязательный или желательный навык
    importance: so.Mapped[int] = so.mapped_column(sa.Integer, default=1)  # Важность навыка от 1 до 10
    
    # Отношения
    vacancy = so.relationship('Vacancy', back_populates='skills')
    skill = so.relationship('Skill', back_populates='vacancy_skills')
    
    def __repr__(self):
        return f'<VacancySkill vacancy_id={self.vacancy_id} skill_id={self.skill_id}>' 