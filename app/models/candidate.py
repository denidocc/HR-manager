from datetime import datetime, timezone
import uuid
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db
from app.utils.encryption import encrypted_property

class Candidate(db.Model):
    __tablename__ = 'candidates'
    
    id: so.Mapped[int] = so.mapped_column(sa.Integer, primary_key=True)
    vacancy_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('vacancies.id'))
    user_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('users.id'))
    stage_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('c_selection_stage.id'))
    full_name: so.Mapped[str] = so.mapped_column(sa.Text)
    _email: so.Mapped[str] = so.mapped_column(sa.Text, index=True, unique=True, nullable=True)
    _phone: so.Mapped[str] = so.mapped_column(sa.Text, index=True, unique=True, nullable=True)
    base_answers: so.Mapped[dict] = so.mapped_column(sa.JSON)
    vacancy_answers: so.Mapped[dict] = so.mapped_column(sa.JSON)
    soft_answers: so.Mapped[dict] = so.mapped_column(sa.JSON)
    resume_path: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    resume_text: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    structured_resume_data: so.Mapped[dict] = so.mapped_column(sa.JSON, default=lambda: {}, nullable=True)
    cover_letter: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    ai_match_percent: so.Mapped[float] = so.mapped_column(sa.Float, nullable=True)
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
    id_c_rejection_reason: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('c_rejection_reason.id'), nullable=True)
    interview_date: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=True)
    hr_comment: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime, default=datetime.utcnow)
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    tracking_code: so.Mapped[str] = so.mapped_column(sa.Text, unique=True)
    gender: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    
    # Свойства для шифрованных полей
    email = encrypted_property('email')
    phone = encrypted_property('phone')
    
    # Определяем составной внешний ключ
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ['user_id', 'stage_id'],
            ['user_selection_stages.user_id', 'user_selection_stages.stage_id'],
            name='fk_candidate_user_selection_stage'
        ),
    )
    
    # Отношения
    vacancy = so.relationship('Vacancy', back_populates='candidates')
    notifications = so.relationship('Notification', back_populates='candidate', cascade='all, delete-orphan')
    c_rejection_reason = so.relationship('C_Rejection_Reason', back_populates='candidates')
    skills = so.relationship('CandidateSkill', back_populates='candidate', cascade='all, delete-orphan')
    user_selection_stage = so.relationship(
        'User_Selection_Stage',
        foreign_keys=[user_id, stage_id],
        primaryjoin="and_(Candidate.user_id==User_Selection_Stage.user_id, "
                   "Candidate.stage_id==User_Selection_Stage.stage_id)",
        back_populates='candidates',
        overlaps="candidates"
    )
    user = so.relationship('User', back_populates='candidates', overlaps="user_selection_stage")
    
    def __repr__(self):
        return f'<Candidate {self.full_name}>'
    
    def to_dict(self):
        """Преобразует объект в словарь"""
        return {
            'id': self.id,
            'vacancy_id': self.vacancy_id,
            'user_id': self.user_id,
            'stage_id': self.stage_id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'base_answers': self.base_answers,
            'vacancy_answers': self.vacancy_answers,
            'soft_answers': self.soft_answers,
            'resume_path': self.resume_path,
            'resume_text': self.resume_text,
            'structured_resume_data': self.structured_resume_data,
            'cover_letter': self.cover_letter,
            'ai_match_percent': self.ai_match_percent,
            'ai_pros': self.ai_pros,
            'ai_cons': self.ai_cons,
            'ai_recommendation': self.ai_recommendation,
            'ai_score_location': self.ai_score_location,
            'ai_score_experience': self.ai_score_experience,
            'ai_score_tech': self.ai_score_tech,
            'ai_score_education': self.ai_score_education,
            'ai_score_comments_location': self.ai_score_comments_location,
            'ai_score_comments_experience': self.ai_score_comments_experience,
            'ai_score_comments_tech': self.ai_score_comments_tech,
            'ai_score_comments_education': self.ai_score_comments_education,
            'ai_mismatch_notes': self.ai_mismatch_notes,
            'ai_data_consistency': self.ai_data_consistency,
            'ai_answer_quality': self.ai_answer_quality,
            'ai_data_completeness': self.ai_data_completeness,
            'ai_analysis_data': self.ai_analysis_data,
            'id_c_rejection_reason': self.id_c_rejection_reason,
            'interview_date': self.interview_date.isoformat() if self.interview_date else None,
            'hr_comment': self.hr_comment,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'tracking_code': self.tracking_code,
            'gender': self.gender,
            'stage': self.user_selection_stage.selection_stage.name if self.user_selection_stage else None,
            'stage_color': self.user_selection_stage.selection_stage.color if self.user_selection_stage else None,
            'stage_status': self.user_selection_stage.selection_stage.selection_status.code if self.user_selection_stage and self.user_selection_stage.selection_stage.selection_status else None
        }
    
    @staticmethod
    def get_valid_stages():
        return ['new', 'interview', 'rejected', 'accepted'] 