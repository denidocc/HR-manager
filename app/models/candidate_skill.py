import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class CandidateSkill(db.Model):
    """Связующая таблица между кандидатами и навыками"""
    __tablename__ = 'candidate_skills'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    candidate_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('candidates.id'), nullable=False)
    skill_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('skills.id'), nullable=False)
    experience_months: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=True)  # Опыт в месяцах
    level: so.Mapped[int] = so.mapped_column(sa.Integer, default=1)  # Уровень навыка от 1 до 5
    extracted_from: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)  # Источник (resume_text, vacancy_answers, etc.)
    
    # Отношения
    candidate = so.relationship('Candidate', back_populates='skills')
    skill = so.relationship('Skill', back_populates='candidate_skills')
    
    def __repr__(self):
        return f'<CandidateSkill candidate_id={self.candidate_id} skill_id={self.skill_id}>' 