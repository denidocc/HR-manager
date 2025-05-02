from datetime import datetime, timezone
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

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
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('users.id'), nullable=True)
    
    # Отношения
    creator = so.relationship('User', back_populates='created_vacancies')
    candidates = so.relationship('Candidate', back_populates='vacancy', cascade='all, delete-orphan')
    c_employment_type = so.relationship('C_Employment_Type', back_populates='vacancies')
    
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
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'creator': self.creator.full_name if self.creator else None
        } 