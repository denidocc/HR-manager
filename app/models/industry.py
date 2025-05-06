import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class Industry(db.Model):
    """Модель для отраслей и индустрий"""
    __tablename__ = 'industries'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False, index=True)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    parent_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('industries.id'), nullable=True)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    # Отношения
    parent = so.relationship('Industry', remote_side=[id], backref='children')
    vacancies = so.relationship('VacancyIndustry', back_populates='industry')
    
    def __repr__(self):
        return f'<Industry {self.name}>' 