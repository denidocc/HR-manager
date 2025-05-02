import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class C_Gender(db.Model):
    __tablename__ = 'c_gender'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    short_name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    # Отношения
    users = so.relationship('User', back_populates='c_gender')
    
    def __repr__(self):
        return f'<C_Gender {self.name}>' 