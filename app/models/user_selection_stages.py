#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db

class User_Selection_Stage(db.Model):
    """Этапы отбора для конкретного пользователя"""
    __tablename__ = 'user_selection_stages'
    
    user_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('users.id'), primary_key=True)
    stage_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('c_selection_stage.id'), primary_key=True)
    order: so.Mapped[int] = so.mapped_column(sa.Integer, default=0)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    
    # Отношения
    user = so.relationship('User', back_populates='selection_stages')
    selection_stage = so.relationship('C_Selection_Stage', back_populates='user_selection_stages')
    candidates = so.relationship('Candidate', back_populates='user_selection_stage', overlaps="user")
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'stage_id': self.stage_id,
            'order': self.order,
            'is_active': self.is_active
        }
    
    def __repr__(self):
        return f'<User_Selection_Stage {self.user_id}:{self.stage_id}>'
    