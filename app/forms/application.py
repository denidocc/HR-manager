#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

class ApplicationForm(FlaskForm):
    """Форма для подачи заявки на вакансию"""
    # Основная информация
    full_name = StringField('ФИО', validators=[
        DataRequired(message='Введите ваше ФИО'),
        Length(min=5, max=100, message='ФИО должно содержать от 5 до 100 символов')
    ])
    
    email = StringField('Email', validators=[
        DataRequired(message='Введите ваш email'),
        Email(message='Введите корректный email')
    ])
    
    phone = StringField('Телефон', validators=[
        DataRequired(message='Введите ваш телефон'),
        Length(min=10, max=20, message='Введите корректный номер телефона')
    ])
    
    # Базовые вопросы
    location = StringField('Город проживания', validators=[
        DataRequired(message='Укажите город проживания')
    ])
    
    experience_years = IntegerField('Опыт работы (лет)', validators=[
        DataRequired(message='Укажите опыт работы'),
        NumberRange(min=0, max=50, message='Опыт работы должен быть от 0 до 50 лет')
    ])
    
    education = SelectField('Образование', 
        choices=[
            ('secondary', 'Среднее'),
            ('vocational', 'Среднее специальное'),
            ('higher', 'Высшее'),
            ('phd', 'Ученая степень')
        ],
        validators=[DataRequired(message='Выберите уровень образования')]
    )
    
    desired_salary = IntegerField('Желаемая зарплата', validators=[
        Optional(),
        NumberRange(min=0, message='Зарплата должна быть положительным числом')
    ])
    
    # Загрузка резюме
    resume = FileField('Резюме', validators=[
        FileRequired(message='Загрузите файл резюме'),
        FileAllowed(['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'], 
                   message='Допустимые форматы: PDF, DOC, DOCX, JPG, PNG')
    ])
    
    # Профессиональные вопросы и вопросы soft skills будут добавлены динамически
    
    submit = SubmitField('Отправить заявку') 