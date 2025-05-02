import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class C_Candidate_Status(db.Model):
    __tablename__ = 'c_candidate_status'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    color_code: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    # Отношения
    candidates = so.relationship('Candidate', back_populates='c_candidate_status')
    
    def __repr__(self):
        return f'<C_Candidate_Status {self.name}>' 