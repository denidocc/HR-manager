from datetime import datetime
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class SystemLog(db.Model):
    __tablename__ = 'system_logs'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    event_type: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    user_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('users.id'), nullable=True)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    ip_address: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=datetime.utcnow)
    
    # Отношения
    user = so.relationship('User', backref='system_logs')
    
    def __repr__(self):
        return f'<SystemLog {self.id}: {self.event_type}>'
    
    @staticmethod
    def log(event_type, description, user_id=None, ip_address=None):
        """
        Создает запись лога в базе данных
        """
        log = SystemLog(
            event_type=event_type,
            description=description,
            user_id=user_id,
            ip_address=ip_address
        )
        db.session.add(log)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Логируем в файл, если не можем записать в БД
            print(f"Error logging to DB: {e}")
        return log 