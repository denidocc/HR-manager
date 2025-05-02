from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    email: so.Mapped[str] = so.mapped_column(sa.Text, index=True, unique=True, nullable=False)
    password_hash: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    role: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    full_name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=datetime.utcnow)
    last_login: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=True)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_hr(self):
        return self.role == 'hr'
    
    def is_candidate(self):
        return self.role == 'candidate'

@login_manager.user_loader
def load_user(id):
    return db.session.get(User, int(id)) 