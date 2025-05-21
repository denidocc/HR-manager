#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

# Ассоциативная таблица для связи "многие-ко-многим" между HR и этапами отбора
user_selection_stages = db.Table('user_selection_stages',
    sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), primary_key=True),
    sa.Column('stage_id', sa.Integer, sa.ForeignKey('c_selection_stage.id'), primary_key=True),
    sa.Column('order', sa.Integer, default=0),  # Порядок для конкретного пользователя
    sa.Column('is_active', sa.Boolean, default=True)
)

class C_Selection_Stage(db.Model):
    """Справочник этапов отбора кандидатов"""
    __tablename__ = 'c_selection_stage'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    color: so.Mapped[str] = so.mapped_column(sa.String(20), default='#6c757d')
    order: so.Mapped[int] = so.mapped_column(sa.Integer, default=0)
    type: so.Mapped[str] = so.mapped_column(sa.String(50), default='standard')
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    # Отношения
    candidates = so.relationship('Candidate', back_populates='selection_stage')
    users = so.relationship('User', secondary=user_selection_stages, back_populates='selection_stages')
    
    def __repr__(self):
        return f'<C_Selection_Stage {self.name}>'
    
    @classmethod
    def create_default_stages(cls):
        """Создание стандартных этапов отбора"""
        stages = [
            {"name": "Новая заявка", "description": "Кандидат только что подал заявку", "color": "#6c757d", "order": 0},
            {"name": "Рассмотрение резюме", "description": "Резюме кандидата на рассмотрении", "color": "#17a2b8", "order": 1},
            {"name": "Тестовое задание", "description": "Кандидат выполняет тестовое задание", "color": "#ffc107", "order": 2},
            {"name": "Собеседование с HR", "description": "Запланировано собеседование с HR-менеджером", "color": "#fd7e14", "order": 3},
            {"name": "Техническое интервью", "description": "Запланировано техническое собеседование", "color": "#6f42c1", "order": 4},
            {"name": "Предложение", "description": "Кандидату сделано предложение", "color": "#20c997", "order": 5},
            {"name": "Принят на работу", "description": "Кандидат принят на работу", "color": "#28a745", "order": 6},
            {"name": "Отказ", "description": "Кандидату отказано", "color": "#dc3545", "order": 7}
        ]
        
        for stage_data in stages:
            # Проверяем, существует ли уже этап с таким именем
            existing_stage = cls.query.filter_by(name=stage_data["name"]).first()
            if not existing_stage:
                stage = cls(**stage_data)
                db.session.add(stage)
        
        db.session.commit() 