#!/usr/bin/env python
# -*- coding: utf-8 -*-
from flask import current_app
from app import db
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, SelectField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, ValidationError
import re
from app.models import C_Education, C_Gender

# Валидатор для телефонных номеров
def validate_phone(form, field):
    """Проверяет, что номер телефона соответствует формату Туркменистана (+993XXXXXXXX)"""
    phone_regex = re.compile(r'^\+993\d{8}$')
    if not phone_regex.match(field.data):
        raise ValidationError('Введите номер телефона в формате +993XXXXXXXX')

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
        Length(min=3, max=100, message='ФИО должно содержать от 3 до 100 символов'),
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
    
    education = SelectField('Образование', validators=[
        DataRequired(message='Выберите уровень образования')
    ])
    
    desired_salary = IntegerField('Желаемая зарплата', validators=[
        Optional(),
        NumberRange(min=0, max=10000000, message='Укажите корректную сумму')
    ])
    
    gender = SelectField('Пол', validators=[
        DataRequired(message='Выберите пол')
    ])
    
    # Поле для загрузки резюме
    resume = FileField('Резюме', validators=[
        FileRequired(message='Загрузите файл резюме'),
        FileAllowed(['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'], 
                   message='Допустимые форматы: PDF, DOC, DOCX, JPG, PNG')
    ])
    
    # Сопроводительное письмо
    cover_letter = TextAreaField('Сопроводительное письмо', validators=[
        Optional(),
        Length(max=3000, message='Сопроводительное письмо не должно превышать 3000 символов')
    ])
    
    # Согласие на обработку персональных данных
    consent = BooleanField('Я согласен на обработку моих персональных данных', validators=[
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
    
    def __init__(self, *args, **kwargs):
        super(ApplicationForm, self).__init__(*args, **kwargs)
        # Заполняем списки выбора динамически при создании формы
        self.education.choices = [(c.id, c.name) for c in C_Education.query.all()]
        self.gender.choices = [(c.id, c.name) for c in C_Gender.query.all()]
    
    submit = SubmitField('Отправить заявку') 