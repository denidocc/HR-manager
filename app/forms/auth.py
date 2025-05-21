#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models.user import User
import re

# Валидатор для телефонных номеров
def validate_phone(form, field):
    """Проверяет, что номер телефона соответствует формату Туркменистана (+993XXXXXXXX)"""
    phone_regex = re.compile(r'^\+993\d{8}$')
    if not phone_regex.match(field.data):
        raise ValidationError('Введите номер телефона в формате +993XXXXXXXX')

class LoginForm(FlaskForm):
    """Форма для входа в систему"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

class RegisterForm(FlaskForm):
    """Форма для регистрации нового пользователя"""
    first_name = StringField('Имя', validators=[DataRequired()])
    last_name = StringField('Фамилия', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[
        DataRequired(),
        Length(min=8, message='Пароль должен содержать минимум 8 символов')
    ])
    password2 = PasswordField('Повторите пароль', validators=[
        DataRequired(),
        EqualTo('password', message='Пароли должны совпадать')
    ])
    role = SelectField('Роль', choices=[
        ('hr', 'HR-менеджер'),
        ('admin', 'Администратор')
    ], validators=[DataRequired()])
    department = StringField('Отдел', validators=[DataRequired()])
    
    def validate_email(self, email):
        """Проверка уникальности email"""
        user = User.query.filter(User.email == email.data).first()
        if user is not None:
            raise ValidationError('Пользователь с таким email уже существует')

class ResetPasswordRequestForm(FlaskForm):
    """Форма запроса на сброс пароля"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Запросить сброс пароля')

    def validate_email(self, email):
        user = User.query.filter(User.email == email.data).first()
        if not user:
            raise ValidationError('Пользователь с таким email не найден')

class ResetPasswordForm(FlaskForm):
    """Форма изменения пароля после сброса"""
    password = PasswordField('Новый пароль', validators=[
        DataRequired(message='Введите новый пароль'),
        Length(min=8, message='Пароль должен содержать не менее 8 символов')
    ])
    password2 = PasswordField('Повторите пароль', validators=[
        DataRequired(message='Повторите пароль'),
        EqualTo('password', message='Пароли должны совпадать')
    ])
    submit = SubmitField('Сохранить пароль')

class PublicRegisterForm(FlaskForm):
    """Форма публичной регистрации HR-менеджера"""
    first_name = StringField('Имя', validators=[
        DataRequired(message='Введите ваше имя'),
        Length(min=2, max=50, message='Имя должно содержать от 2 до 50 символов')
    ])
    
    last_name = StringField('Фамилия', validators=[
        DataRequired(message='Введите вашу фамилию'),
        Length(min=2, max=50, message='Фамилия должна содержать от 2 до 50 символов')
    ])
    
    email = StringField('Email', validators=[
        DataRequired(message='Введите email'),
        Email(message='Введите корректный email')
    ])
    
    phone = StringField('Телефон', validators=[
        DataRequired(message='Введите ваш телефон'),
        Length(min=10, max=20, message='Введите корректный номер телефона'),
        validate_phone
    ])
    
    password = PasswordField('Пароль', validators=[
        DataRequired(message='Введите пароль'),
        Length(min=8, message='Пароль должен содержать не менее 8 символов')
    ])
    
    password2 = PasswordField('Повторите пароль', validators=[
        DataRequired(message='Повторите пароль'),
        EqualTo('password', message='Пароли должны совпадать')
    ])
    
    company = StringField('Компания', validators=[
        DataRequired(message='Введите название компании'),
        Length(min=2, max=100, message='Название компании должно содержать от 2 до 100 символов')
    ])
    
    position = StringField('Должность', validators=[
        DataRequired(message='Введите вашу должность'),
        Length(min=2, max=100, message='Должность должна содержать от 2 до 100 символов')
    ])
    
    consent = BooleanField('Я согласен с условиями использования сервиса', validators=[
        DataRequired(message='Необходимо принять условия использования')
    ])
    
    submit = SubmitField('Зарегистрироваться') 