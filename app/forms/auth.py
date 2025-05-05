#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models.user import User

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
    """Форма для сброса пароля"""
    password = PasswordField('Новый пароль', validators=[
        DataRequired(),
        Length(min=8, message='Пароль должен содержать минимум 8 символов')
    ])
    password2 = PasswordField('Повторите пароль', validators=[
        DataRequired(),
        EqualTo('password', message='Пароли должны совпадать')
    ])
    submit = SubmitField('Сохранить новый пароль') 