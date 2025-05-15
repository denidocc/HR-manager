from datetime import datetime, timezone
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db
from app.models.c_employment_type import C_Employment_Type

class Vacancy(db.Model):
    __tablename__ = 'vacancies'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    title: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False, index=True)
    id_c_employment_type: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('c_employment_type.id'), nullable=False, index=True)
    description_tasks: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    description_conditions: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    ideal_profile: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    questions_json: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: [])
    soft_questions_json: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: [])
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    status: so.Mapped[str] = so.mapped_column(sa.Text, default='active')  # active, closed, archived
    location: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)  # город или регион
    difficulty_level: so.Mapped[str] = so.mapped_column(sa.Text, default='medium')  # easy, medium, hard
    target_time_to_fill: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=True)  # целевое время на закрытие в днях
    recruitment_budget: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=True)  # бюджет на наём
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    closed_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=True)  # дата закрытия вакансии
    created_by: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('users.id'), nullable=True)
    company_values: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    
    # Новые поля для отслеживания использования ИИ
    is_ai_generated: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)  # Использовался ли ИИ для генерации
    ai_generation_date: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=True)  # Дата генерации с помощью ИИ
    ai_generation_prompt: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)  # Запрос, использованный для генерации
    ai_generation_metadata: so.Mapped[dict] = so.mapped_column(sa.JSON, nullable=True)  # Дополнительные метаданные о генерации
    
    # Отношения
    creator = so.relationship('User', back_populates='created_vacancies')
    candidates = so.relationship('Candidate', back_populates='vacancy', cascade='all, delete-orphan')
    c_employment_type = so.relationship('C_Employment_Type', back_populates='vacancies')
    skills = so.relationship('VacancySkill', back_populates='vacancy', cascade='all, delete-orphan')
    industries = so.relationship('VacancyIndustry', back_populates='vacancy', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Vacancy {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'employment_type': self.c_employment_type.name if self.c_employment_type else None,
            'description_tasks': self.description_tasks,
            'description_conditions': self.description_conditions,
            'ideal_profile': self.ideal_profile,
            'questions_json': self.questions_json,
            'soft_questions_json': self.soft_questions_json,
            'is_active': self.is_active,
            'status': self.status,
            'location': self.location,
            'difficulty_level': self.difficulty_level,
            'target_time_to_fill': self.target_time_to_fill,
            'recruitment_budget': self.recruitment_budget,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'creator': self.creator.full_name if self.creator else None,
            'is_ai_generated': self.is_ai_generated,
            'ai_generation_date': self.ai_generation_date.isoformat() if self.ai_generation_date else None
        } 