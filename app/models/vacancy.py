from datetime import datetime
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class Vacancy(db.Model):
    __tablename__ = 'vacancies'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    title: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False, index=True)
    employment_type: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    description_tasks: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    description_conditions: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    ideal_profile: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    questions_json: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: [])
    soft_questions_json: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: [])
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=datetime.utcnow)
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('users.id'), nullable=True)
    
    # Отношения
    creator = so.relationship('User', backref='created_vacancies')
    candidates = so.relationship('Candidate', back_populates='vacancy', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Vacancy {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'employment_type': self.employment_type,
            'description_tasks': self.description_tasks,
            'description_conditions': self.description_conditions,
            'ideal_profile': self.ideal_profile,
            'questions_json': self.questions_json,
            'soft_questions_json': self.soft_questions_json,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 