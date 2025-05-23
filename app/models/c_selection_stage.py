#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class C_Selection_Stage(db.Model):
    """Справочник этапов отбора кандидатов"""
    __tablename__ = 'c_selection_stage'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    color: so.Mapped[str] = so.mapped_column(sa.Text, default='#6c757d')
    order: so.Mapped[int] = so.mapped_column(sa.Integer, default=0)
    is_standard: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    id_c_selection_status: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('c_selection_status.id'), nullable=False)
    
    # Отношения
    user_selection_stages = so.relationship('User_Selection_Stage', back_populates='selection_stage')
    status = so.relationship('C_Selection_Status', back_populates='selection_stages')
    
    def __repr__(self):
        return f'<C_Selection_Stage {self.name}>'
    
    @classmethod
    def create_default_stages(cls):
        """Создание стандартных этапов отбора"""
        from app.models.c_selection_status import C_Selection_Status
        
        # Убедимся, что статусы созданы
        C_Selection_Status.create_default_statuses()
        
        # Получаем статусы
        unknown_status = C_Selection_Status.query.filter_by(code='UNKNOWN').first()
        new_status = C_Selection_Status.query.filter_by(code='NEW').first()
        in_progress_status = C_Selection_Status.query.filter_by(code='IN_PROGRESS').first()
        reject_status = C_Selection_Status.query.filter_by(code='REJECT').first()
        accept_status = C_Selection_Status.query.filter_by(code='ACCEPT').first()
        
        stages = [
            {
                "name": "Новая заявка",
                "description": "Кандидат только что подал заявку",
                "color": "#6c757d",
                "order": 0,
                "is_standard": True,
                "id_c_selection_status": new_status.id
            },
            {
                "name": "Рассмотрение резюме",
                "description": "Резюме кандидата на рассмотрении",
                "color": "#17a2b8",
                "order": 1,
                "is_standard": True,
                "id_c_selection_status": in_progress_status.id
            },
            {
                "name": "Тестовое задание",
                "description": "Кандидат выполняет тестовое задание",
                "color": "#ffc107",
                "order": 2,
                "is_standard": True,
                "id_c_selection_status": in_progress_status.id
            },
            {
                "name": "Собеседование с HR",
                "description": "Запланировано собеседование с HR-менеджером",
                "color": "#fd7e14",
                "order": 3,
                "is_standard": True,
                "id_c_selection_status": in_progress_status.id
            },
            {
                "name": "Техническое интервью",
                "description": "Запланировано техническое собеседование",
                "color": "#6f42c1",
                "order": 4,
                "is_standard": True,
                "id_c_selection_status": in_progress_status.id
            },
            {
                "name": "Принят на работу",
                "description": "Кандидат принят на работу",
                "color": "#28a745",
                "order": 6,
                "is_standard": True,
                "id_c_selection_status": accept_status.id
            },
            {
                "name": "Отказ",
                "description": "Кандидату отказано",
                "color": "#dc3545",
                "order": 7,
                "is_standard": True,
                "id_c_selection_status": reject_status.id
            }
        ]
        
        for stage_data in stages:
            # Проверяем, существует ли уже этап с таким именем
            existing_stage = cls.query.filter_by(name=stage_data["name"]).first()
            if not existing_stage:
                stage = cls(**stage_data)
                db.session.add(stage)
        
        db.session.commit() 