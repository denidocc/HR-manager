from datetime import datetime, timezone
from flask_login import UserMixin
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db, login_manager, argon2
from app.utils.encryption import encrypted_property
from app.models.user_selection_stages import User_Selection_Stage

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    _email: so.Mapped[str] = so.mapped_column(sa.Text, index=True, unique=True, nullable=False)
    _phone: so.Mapped[str] = so.mapped_column(sa.Text, index=True, unique=True, nullable=True)
    password_hash: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    role: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    full_name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    company: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    position: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    id_c_gender: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('c_gender.id'), index=True, nullable=True)
    id_c_user_status: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('c_user_status.id'), index=True, default=1)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=True)
    avatar_path: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    # Свойства для шифрованных полей
    email = encrypted_property('email')
    phone = encrypted_property('phone')
    
    # Отношения
    c_gender = so.relationship('C_Gender', back_populates='users')
    c_user_status = so.relationship('C_User_Status', back_populates='users')
    created_vacancies = so.relationship('Vacancy', back_populates='creator')
    system_logs = so.relationship('SystemLog', back_populates='user')
    selection_stages = so.relationship('User_Selection_Stage', back_populates='user')
    candidates = so.relationship('Candidate', back_populates='user', overlaps="user_selection_stage")
    
    def __repr__(self):
        return f'<User {self._email}>'
    
    def set_password(self, password):
        self.password_hash = argon2.generate_password_hash(password)
    
    def check_password(self, password):
        return argon2.check_password_hash(self.password_hash, password)
    
    @property
    def is_hr(self):
        return self.role == 'hr'
    
    @property
    def is_candidate(self):
        return self.role == 'candidate'
    
    def get_selection_stages(self):
        """Получает этапы отбора пользователя, или стандартные если у него их нет"""
        from app.models.c_selection_stage import C_Selection_Stage
        
        # Получаем этапы через связь User_Selection_Stage
        user_stages = User_Selection_Stage.query.filter_by(user_id=self.id).order_by(User_Selection_Stage.order).all()
        
        if user_stages:
            # Возвращаем этапы отбора из связей
            return [stage.selection_stage for stage in user_stages]
        
        # Если у пользователя нет собственных этапов, возвращаем стандартные
        return C_Selection_Stage.query.filter_by(is_standard=True).order_by(C_Selection_Stage.order).all()
    
    def initialize_default_stages(self):
        """Инициализирует стандартные этапы отбора для нового пользователя"""
        from app.models.c_selection_stage import C_Selection_Stage
        from app.models.user_selection_stages import User_Selection_Stage
        
        if not self.selection_stages:
            default_stages = C_Selection_Stage.query.filter_by(is_standard=True).order_by(C_Selection_Stage.order).all()
            for stage in default_stages:
                user_stage = User_Selection_Stage(
                    user_id=self.id,
                    stage_id=stage.id,
                    order=stage.order,
                    is_active=True
                )
                db.session.add(user_stage)
            db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'full_name': self.full_name,
            'company': self.company,
            'position': self.position,
            'gender': self.c_gender.name if self.c_gender else None,
            'status': self.c_user_status.name if self.c_user_status else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }

@login_manager.user_loader
def load_user(id):
    return db.session.get(User, int(id)) 