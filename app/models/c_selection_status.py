#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class C_Selection_Status(db.Model):
    """Справочник статусов этапов отбора кандидатов"""
    __tablename__ = 'c_selection_status'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    code: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False, unique=True)  # UNKNOWN, NEW, REJECT, ACCEPT и т.д.
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    order: so.Mapped[int] = so.mapped_column(sa.Integer, default=0)
    
    # Отношения
    selection_stages = so.relationship('C_Selection_Stage', back_populates='status')
    
    def __repr__(self):
        return f'<C_Selection_Status {self.name}>'
    
    @classmethod
    def create_default_statuses(cls):
        """Создание стандартных статусов этапов отбора"""
        statuses = [
            {"name": "Неизвестно", "code": "UNKNOWN", "description": "Статус не определен", "order": 0},
            {"name": "Новый", "code": "NEW", "description": "Новый этап отбора", "order": 1},
            {"name": "В процессе", "code": "IN_PROGRESS", "description": "Этап в процессе выполнения", "order": 2},
            {"name": "Отклонен", "code": "REJECT", "description": "Кандидат отклонен", "order": 3},
            {"name": "Принят", "code": "ACCEPT", "description": "Кандидат принят", "order": 4}
        ]
        
        for status_data in statuses:
            # Проверяем, существует ли уже статус с таким кодом
            existing_status = cls.query.filter_by(code=status_data["code"]).first()
            if not existing_status:
                status = cls(**status_data)
                db.session.add(status)
        
        db.session.commit() 