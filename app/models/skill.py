import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class Skill(db.Model):
    """Модель для навыков (для любых типов профессий)"""
    __tablename__ = 'skills'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False, index=True)
    normalized_name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False, index=True)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    category_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('skill_categories.id'), nullable=False)
    synonyms: so.Mapped[list] = so.mapped_column(sa.JSON, default=lambda: [])
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    frequency: so.Mapped[int] = so.mapped_column(sa.Integer, default=0)  # Частота встречаемости в резюме
    
    # Отношения
    category = so.relationship('SkillCategory', back_populates='skills')
    vacancy_skills = so.relationship('VacancySkill', back_populates='skill')
    candidate_skills = so.relationship('CandidateSkill', back_populates='skill')
    
    def __repr__(self):
        return f'<Skill {self.name}>' 