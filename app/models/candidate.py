from datetime import datetime, timezone
import uuid
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db
from app.utils.encryption import encrypted_property

class Candidate(db.Model):
    __tablename__ = 'candidates'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    vacancy_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('vacancies.id'), nullable=False)
    full_name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    _email: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False, index=True)
    _phone: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    base_answers: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {})
    vacancy_answers: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {})
    soft_answers: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {})
    resume_path: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    resume_text: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    structured_resume_data: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {}, nullable=True)
    cover_letter: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
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
    ai_data_consistency: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {}, nullable=True)
    ai_answer_quality: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {}, nullable=True)
    ai_data_completeness: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {}, nullable=True)
    ai_analysis_data: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {}, nullable=True)
    id_c_selection_stage: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('c_selection_stage.id'), nullable=False)
    id_c_rejection_reason: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('c_rejection_reason.id'), nullable=True)
    interview_date: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=True)
    hr_comment: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    tracking_code: so.Mapped[str] = so.mapped_column(sa.Text, unique=True)
    gender: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    
    # Свойства для шифрованных полей
    email = encrypted_property('email')
    phone = encrypted_property('phone')
    
    # Отношения
    vacancy = so.relationship('Vacancy', back_populates='candidates')
    notifications = so.relationship('Notification', back_populates='candidate', cascade='all, delete-orphan')
    c_rejection_reason = so.relationship('C_Rejection_Reason', back_populates='candidates')
    skills = so.relationship('CandidateSkill', back_populates='candidate', cascade='all, delete-orphan')
    selection_stage = so.relationship('C_Selection_Stage', back_populates='candidates')
    
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
            'stage': self.selection_stage.name if self.selection_stage else 'Заявка подана',
            'interview_date': self.interview_date.isoformat() if self.interview_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'tracking_code': self.tracking_code
        }
    
    @staticmethod
    def get_valid_stages():
        return ['new', 'interview', 'rejected', 'accepted'] 