from datetime import datetime
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    candidate_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('candidates.id'), nullable=False)
    type: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    message: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    email_sent: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=datetime.utcnow)
    
    # Отношения
    candidate = so.relationship('Candidate', back_populates='notifications')
    
    def __repr__(self):
        return f'<Notification {self.id} for Candidate {self.candidate_id}>'
    
    @staticmethod
    def get_notification_types():
        return ['application_received', 'status_update', 'interview_invitation', 'rejection', 'offer', 'ai_analysis_completed']
    
    def to_dict(self):
        return {
            'id': self.id,
            'candidate_id': self.candidate_id,
            'type': self.type,
            'message': self.message,
            'email_sent': self.email_sent,
            'created_at': self.created_at.isoformat() if self.created_at else None
        } 