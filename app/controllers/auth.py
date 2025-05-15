#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app import db, argon2
from app.models.user import User
from app.models.system_log import SystemLog
from app.forms.auth import LoginForm, RegisterForm, ResetPasswordRequestForm, ResetPasswordForm, PublicRegisterForm
from app.utils.email_service import send_password_reset_email
from functools import wraps
from sqlalchemy import func, cast
import sqlalchemy as sa
from app.utils.decorators import profile_time

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/auth')

def admin_required(f):
    """Декоратор для проверки прав администратора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Доступ запрещен. Требуются права администратора.', 'danger')
            return redirect(url_for('auth_bp.login'))
        return f(*args, **kwargs)
    return decorated_function

def hr_required(f):
    """Декоратор для проверки прав HR-менеджера"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'hr':
            flash('Доступ запрещен. Требуются права HR-менеджера.', 'danger')
            return redirect(url_for('auth_bp.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
@profile_time
def login():
    """Страница авторизации для HR-менеджеров"""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('dashboard.index'))
        else:
            return redirect(url_for('dashboard.hr_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Ищем пользователя с указанным email через дешифрование значения в базе
        user = db.session.query(User).filter(
            func.pgp_sym_decrypt(
                cast(User._email, sa.LargeBinary),
                current_app.config['ENCRYPTION_KEY'],
                current_app.config.get('ENCRYPTION_OPTIONS', '')
            ) == form.email.data
        ).first()
        
        if user and user.check_password(form.password.data):
            # Проверяем статус пользователя
            if user.id_c_user_status != 1:  # Если не активен
                if user.id_c_user_status == 2:
                    flash('Ваша учетная запись ожидает подтверждения администратором', 'warning')
                elif user.id_c_user_status == 3:
                    flash('Ваша заявка на регистрацию была отклонена', 'danger')
                else:
                    flash('Ваша учетная запись неактивна', 'danger')
                return render_template('auth/login.html', form=form, title='Вход в систему')
            
            login_user(user, remember=form.remember_me.data)
            
            # Логирование успешного входа
            SystemLog.log(
                event_type="login",
                description=f"Вход в систему HR-менеджера",
                user_id=user.id,
                ip_address=request.remote_addr
            )
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
                
            # Перенаправляем пользователя на нужную панель управления в зависимости от роли
            if user.role == 'admin':
                return redirect(url_for('dashboard.index'))
            else:
                return redirect(url_for('dashboard.hr_dashboard'))
        
        flash('Неверный email или пароль', 'danger')
    
    return render_template('auth/login.html', form=form, title='Вход в систему')

@auth_bp.route('/register', methods=['GET', 'POST'])
@profile_time
@login_required
@admin_required
def register():
    """Регистрация нового HR-менеджера (только администраторами)"""
    form = RegisterForm()
    
    if form.validate_on_submit():
        # Создаем нового пользователя
        user = User()
        user.email = form.email.data
        user.phone = form.phone.data
        user.set_password(form.password.data)
        user.role = form.role.data
        user.full_name = f"{form.first_name.data} {form.last_name.data}"
        # Дополнительные поля могут быть добавлены позже
        
        # Сохраняем в базу
        db.session.add(user)
        db.session.commit()
        
        # Логирование регистрации нового пользователя
        SystemLog.log(
            event_type="user_register",
            description=f"Регистрация нового пользователя с ролью {form.role.data}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        flash(f'Пользователь {user.full_name} успешно зарегистрирован!', 'success')
        return redirect(url_for('dashboard_bp.users'))
    
    return render_template('auth/register.html', form=form, title='Регистрация пользователя')

@auth_bp.route('/register-hr', methods=['GET', 'POST'])
@profile_time
def register_hr():
    """Публичная регистрация нового HR-менеджера"""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('dashboard.index'))
        else:
            return redirect(url_for('dashboard.hr_dashboard'))
    
    form = PublicRegisterForm()
    
    if form.validate_on_submit():
        # Проверяем, существует ли пользователь с таким email через дешифрование
        user = db.session.query(User).filter(
            func.pgp_sym_decrypt(
                cast(User._email, sa.LargeBinary),
                current_app.config['ENCRYPTION_KEY'],
                current_app.config.get('ENCRYPTION_OPTIONS', '')
            ) == form.email.data
        ).first()
        
        if user:
            flash('Email уже зарегистрирован в системе', 'danger')
        else:
            # Создаем нового пользователя
            user = User()
            user.email = form.email.data
            user.set_password(form.password.data)
            user.role = 'hr'  # По умолчанию роль HR
            user.full_name = f"{form.first_name.data} {form.last_name.data}"
            user.company = form.company.data
            user.position = form.position.data
            user.id_c_user_status = 2  # Статус "Ожидает подтверждения"
            
            # Сохраняем в базу
            db.session.add(user)
            db.session.commit()
            
            # Логирование регистрации
            SystemLog.log(
                event_type="user_register_public",
                description=f"Публичная регистрация нового HR-менеджера: {user.full_name}",
                ip_address=request.remote_addr
            )
            
            flash('Ваша заявка на регистрацию успешно отправлена. После проверки администратором вы получите доступ к системе.', 'success')
            return redirect(url_for('auth_bp.login'))
    
    return render_template('auth/register_hr.html', form=form, title='Регистрация HR-менеджера')

@auth_bp.route('/logout')
@profile_time
@login_required
def logout():
    """Выход из системы"""
    # Логирование выхода
    SystemLog.log(
        event_type="logout",
        description=f"Выход из системы HR-менеджера",
        user_id=current_user.id,
        ip_address=request.remote_addr
    )
    
    logout_user()
    return redirect(url_for('auth_bp.login'))

@auth_bp.route('/reset_password_request', methods=['GET', 'POST'])
@profile_time
def reset_password_request():
    """Запрос на сброс пароля"""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('dashboard.index'))
        else:
            return redirect(url_for('dashboard.hr_dashboard'))
    
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        # Ищем пользователя с указанным email через дешифрование
        user = db.session.query(User).filter(
            func.pgp_sym_decrypt(
                cast(User._email, sa.LargeBinary),
                current_app.config['ENCRYPTION_KEY'],
                current_app.config.get('ENCRYPTION_OPTIONS', '')
            ) == form.email.data
        ).first()
        
        if user:
            send_password_reset_email(user)
            
            # Логирование запроса на сброс пароля
            SystemLog.log(
                event_type="password_reset_request",
                description=f"Запрос на сброс пароля",
                user_id=user.id,
                ip_address=request.remote_addr
            )
            
        flash('Инструкции по сбросу пароля отправлены на email', 'info')
        return redirect(url_for('auth_bp.login'))
    
    return render_template('auth/reset_password_request.html', form=form, title='Сброс пароля')

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
@profile_time
def reset_password(token):
    """Сброс пароля по токену"""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('dashboard.index'))
        else:
            return redirect(url_for('dashboard.hr_dashboard'))
    
    user = User.verify_reset_password_token(token)
    if not user:
        flash('Недействительный или просроченный токен сброса пароля', 'danger')
        return redirect(url_for('auth_bp.login'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        
        # Логирование успешного сброса пароля
        SystemLog.log(
            event_type="password_reset_success",
            description=f"Успешный сброс пароля",
            user_id=user.id,
            ip_address=request.remote_addr
        )
        
        flash('Ваш пароль был успешно изменен', 'success')
        return redirect(url_for('auth_bp.login'))
    
    return render_template('auth/reset_password.html', form=form, title='Новый пароль') 