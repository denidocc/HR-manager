import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class SkillCategory(db.Model):
    """Модель для категорий навыков (технические, soft skills, индустриальные и т.д.)"""
    __tablename__ = 'skill_categories'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    # Отношения
    skills = so.relationship('Skill', back_populates='category', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<SkillCategory {self.name}>' 