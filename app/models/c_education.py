from app import db
import sqlalchemy as sa
import sqlalchemy.orm as so

class C_Education(db.Model):
    __tablename__ = 'c_education'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    short_name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    def __repr__(self):
        return f'<C_Education {self.name}>' 