import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class C_User_Status(db.Model):
    __tablename__ = 'c_user_status'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    # Отношения
    users = so.relationship('User', back_populates='c_user_status')
    
    def __repr__(self):
        return f'<C_User_Status {self.name}>' 