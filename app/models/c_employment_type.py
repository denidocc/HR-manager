import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class C_Employment_Type(db.Model):
    __tablename__ = 'c_employment_type'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    # Отношения
    vacancies = so.relationship('Vacancy', back_populates='c_employment_type')
    
    def __repr__(self):
        return f'<C_Employment_Type {self.name}>' 