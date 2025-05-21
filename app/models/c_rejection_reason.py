#!/usr/bin/env python
# -*- coding: utf-8 -*-

from app import db
import sqlalchemy as sa
import sqlalchemy.orm as so
from app.models.candidate import Candidate

class C_Rejection_Reason(db.Model):
    """Справочник причин отклонения кандидатов"""
    __tablename__ = 'c_rejection_reason'
    
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    is_default: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    order: so.Mapped[int] = so.mapped_column(sa.Integer, default=0)
    
    # Добавляем обратную связь с кандидатами
    candidates: so.Mapped[list["Candidate"]] = so.relationship(back_populates="rejection_reason")
    
    def __repr__(self):
        return f'<C_Rejection_Reason {self.name}>' 