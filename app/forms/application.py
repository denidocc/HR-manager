#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, SelectField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, ValidationError
import re

# Валидатор для телефонных номеров
def validate_phone(form, field):
    """Проверяет, что номер телефона имеет допустимый формат"""
    phone_regex = re.compile(r'^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$')
    if not phone_regex.match(field.data):
        raise ValidationError('Введите корректный номер телефона')

# Валидатор для имени
def validate_name(form, field):
    """Проверяет, что имя содержит только допустимые символы"""
    if not re.match(r'^[а-яА-ЯёЁa-zA-Z\s\-]+$', field.data):
        raise ValidationError('ФИО должно содержать только буквы, пробелы и дефисы')

class ApplicationForm(FlaskForm):
    """Форма для подачи заявки на вакансию"""
    # Основная информация
    full_name = StringField('ФИО', validators=[
        DataRequired(message='Введите ваше ФИО'),
        Length(min=5, max=100, message='ФИО должно содержать от 5 до 100 символов'),
        validate_name
    ])
    
    email = StringField('Email', validators=[
        DataRequired(message='Введите ваш email'),
        Email(message='Введите корректный email')
    ])
    
    phone = StringField('Телефон', validators=[
        DataRequired(message='Введите ваш телефон'),
        Length(min=10, max=20, message='Введите корректный номер телефона'),
        validate_phone
    ])
    
    # Базовые вопросы
    location = StringField('Город проживания', validators=[
        DataRequired(message='Укажите город проживания'),
        Length(min=2, max=100, message='Название города должно содержать от 2 до 100 символов')
    ])
    
    experience_years = IntegerField('Опыт работы (лет)', validators=[
        DataRequired(message='Укажите опыт работы'),
        NumberRange(min=0, max=50, message='Опыт работы должен быть от 0 до 50 лет')
    ])
    
    education = SelectField('Образование', 
        choices=[
            ('', 'Выберите уровень образования'),
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
    
    # Сопроводительное письмо (опционально)
    cover_letter = TextAreaField('Сопроводительное письмо', validators=[
        Optional(),
        Length(max=2000, message='Сопроводительное письмо не должно превышать 2000 символов')
    ])
    
    # Согласие на обработку данных
    consent = BooleanField('Я согласен на обработку персональных данных', validators=[
        DataRequired(message='Необходимо согласие на обработку персональных данных')
    ])
    
    # Примечание: Профессиональные вопросы и вопросы soft skills добавляются динамически 
    # в контроллере на основе vacancy.questions_json и vacancy.soft_questions_json.
    # Каждый вопрос имеет формат: vacancy_question_{id} или soft_question_{id}
    
    def validate_resume(self, field):
        """Дополнительная валидация для файла резюме"""
        if field.data:
            # Проверка размера файла (5MB)
            if len(field.data.read()) > 5 * 1024 * 1024:
                field.data.seek(0)  # Возвращаем указатель файла в начало
                raise ValidationError('Размер файла не должен превышать 5MB')
            field.data.seek(0)  # Возвращаем указатель файла в начало
    
    submit = SubmitField('Отправить заявку') 