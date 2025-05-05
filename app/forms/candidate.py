#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateTimeField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class CandidateCommentForm(FlaskForm):
    """Форма для добавления комментария к кандидату"""
    comment = TextAreaField('Комментарий HR-менеджера', validators=[
        DataRequired(message='Введите комментарий'),
        Length(min=10, message='Комментарий должен содержать минимум 10 символов')
    ])
    submit = SubmitField('Сохранить комментарий')

class CandidateStatusForm(FlaskForm):
    """Форма для изменения статуса кандидата"""
    id_c_candidate_status = SelectField('Статус', 
        validators=[DataRequired(message='Выберите статус')], 
        coerce=int
    )
    interview_date = DateTimeField('Дата собеседования', 
        format='%Y-%m-%dT%H:%M', 
        validators=[Optional()]
    )
    submit = SubmitField('Изменить статус') 