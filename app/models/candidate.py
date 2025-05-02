from datetime import datetime
import uuid
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class Candidate(db.Model):
    __tablename__ = 'candidates'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    vacancy_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('vacancies.id'), nullable=False)
    full_name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    email: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False, index=True)
    phone: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    base_answers: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {})
    vacancy_answers: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {})
    soft_answers: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {})
    resume_path: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    resume_text: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    ai_match_percent: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=True)
    ai_pros: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    ai_cons: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    ai_recommendation: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    ai_score_location: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=True)
    ai_score_experience: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=True)
    ai_score_tech: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=True)
    ai_score_education: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=True)
    ai_score_comments_location: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    ai_score_comments_experience: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    ai_score_comments_tech: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    ai_score_comments_education: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    ai_mismatch_notes: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    status: so.Mapped[str] = so.mapped_column(sa.Text, default='new')
    interview_date: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=True)
    hr_comment: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=datetime.utcnow)
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    tracking_code: so.Mapped[str] = so.mapped_column(sa.Text, default=lambda: str(uuid.uuid4()), unique=True)
    
    # Отношения
    vacancy = so.relationship('Vacancy', back_populates='candidates')
    notifications = so.relationship('Notification', back_populates='candidate', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Candidate {self.full_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'vacancy_id': self.vacancy_id,
            'vacancy_title': self.vacancy.title if self.vacancy else None,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'ai_match_percent': self.ai_match_percent,
            'status': self.status,
            'interview_date': self.interview_date.isoformat() if self.interview_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'tracking_code': self.tracking_code
        }
    
    @staticmethod
    def get_valid_statuses():
        return ['new', 'interview', 'rejected', 'accepted'] 