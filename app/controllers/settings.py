#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.c_selection_stage import C_Selection_Stage
from app.models.user_selection_stages import User_Selection_Stage
from app.models.c_selection_status import C_Selection_Status
from app.forms.selection_stage import SelectionStageForm
from functools import wraps
import json
import sqlalchemy as sa
from sqlalchemy import cast, func

# Создаем Blueprint для настроек
settings_bp = Blueprint('settings_bp', __name__, url_prefix='/settings')

# Декоратор для проверки, что пользователь является HR-менеджером
def hr_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_hr:
            flash('Доступ запрещен. Требуются права HR-менеджера.', 'danger')
            return redirect(url_for('dashboard_bp.index'))
        return f(*args, **kwargs)
    return decorated_function

@settings_bp.route('/', methods=['GET'])
@login_required
@hr_required
def index():
    """Главная страница настроек"""
    return render_template('settings/index.html', title='Настройки')

@settings_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@hr_required
def profile():
    """Настройки профиля пользователя"""
    if request.method == 'POST':
        # Обновление данных профиля
        try:
            current_user.full_name = request.form.get('full_name')
            current_user.email = request.form.get('email')
            current_user.phone = request.form.get('phone')
            
            # Обновление пароля, если он был предоставлен
            new_password = request.form.get('new_password')
            if new_password and len(new_password) >= 6:
                current_user.set_password(new_password)
            
            db.session.commit()
            flash('Профиль успешно обновлен!', 'success')
            
            # После успешного сохранения получаем обновленные данные через запрос
            user = db.session.query(
                User.id, 
                User.full_name, 
                func.pgp_sym_decrypt(
                    cast(User._email, sa.LargeBinary),
                    current_app.config['ENCRYPTION_KEY'],
                    current_app.config.get('ENCRYPTION_OPTIONS', '')
                ).label('email'),
                func.pgp_sym_decrypt(
                    cast(User._phone, sa.LargeBinary),
                    current_app.config['ENCRYPTION_KEY'],
                    current_app.config.get('ENCRYPTION_OPTIONS', '')
                ).label('phone')).filter(User.id == current_user.id).first()
            
            full_name = user.full_name
            email = user.email
            phone = user.phone if user.phone else ''
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Ошибка при обновлении профиля: {str(e)}")
            flash('Произошла ошибка при обновлении профиля.', 'danger')
            
            # В случае ошибки получаем текущие данные через запрос
            user = db.session.query(
                User.id, 
                User.full_name, 
                func.pgp_sym_decrypt(
                    cast(User._email, sa.LargeBinary),
                    current_app.config['ENCRYPTION_KEY'],
                    current_app.config.get('ENCRYPTION_OPTIONS', '')
                ).label('email'),
                func.pgp_sym_decrypt(
                    cast(User._phone, sa.LargeBinary),
                    current_app.config['ENCRYPTION_KEY'],
                    current_app.config.get('ENCRYPTION_OPTIONS', '')
                ).label('phone')).filter(User.id == current_user.id).first()
            
            full_name = user.full_name
            email = user.email
            phone = user.phone if user.phone else ''
    else:
        user = db.session.query(
            User.id, 
            User.full_name, 
            func.pgp_sym_decrypt(
                cast(User._email, sa.LargeBinary),
                current_app.config['ENCRYPTION_KEY'],
                current_app.config.get('ENCRYPTION_OPTIONS', '')
            ).label('email'),
            func.pgp_sym_decrypt(
                cast(User._phone, sa.LargeBinary),
                current_app.config['ENCRYPTION_KEY'],
                current_app.config.get('ENCRYPTION_OPTIONS', '')
            ).label('phone')).filter(User.id == current_user.id).first()
        
        full_name = user.full_name
        email = user.email
        phone = user.phone if user.phone else ''
            
    return render_template('settings/profile.html', title='Настройки профиля', full_name=full_name, email=email, phone=phone)

@settings_bp.route('/selection-stages', methods=['GET', 'POST'])
@login_required
@hr_required
def selection_stages():
    """Настройки этапов отбора кандидатов для текущего HR-менеджера"""
    # Получаем этапы отбора текущего пользователя или стандартные, если нет собственных
    stages = current_user.get_selection_stages()
    
    # Создаем форму
    form = SelectionStageForm()
    
    # Заполняем choices для SelectField
    available_stages = C_Selection_Stage.query.filter_by(is_standard=True).all()
    form.stage.choices = [(stage.id, stage.name) for stage in available_stages]
    
    if form.validate_on_submit():
        try:
            # Получаем выбранный этап
            stage = C_Selection_Stage.query.get(form.stage.data)
            if not stage:
                flash('Выбранный этап не найден', 'danger')
                return redirect(url_for('settings_bp.selection_stages'))
            
            # Проверяем, не добавлен ли уже этот этап
            existing_stage = User_Selection_Stage.query.filter_by(
                user_id=current_user.id,
                stage_id=stage.id
            ).first()
            
            if existing_stage:
                flash('Этот этап уже добавлен в ваши этапы отбора', 'warning')
                return redirect(url_for('settings_bp.selection_stages'))
            
            # Получаем максимальный порядок
            max_order = db.session.query(func.max(User_Selection_Stage.order))\
                .filter_by(user_id=current_user.id).scalar() or 0
            
            # Создаем новую связь
            user_stage = User_Selection_Stage(
                user_id=current_user.id,
                stage_id=stage.id,
                order=max_order + 1,
                is_active=form.is_active.data
            )
            
            db.session.add(user_stage)
            db.session.commit()
            
            flash('Этап отбора успешно добавлен!', 'success')
            return redirect(url_for('settings_bp.selection_stages'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Ошибка при добавлении этапа отбора: {str(e)}")
            flash('Произошла ошибка при добавлении этапа отбора.', 'danger')
    
    return render_template('settings/selection_stages.html', 
                         title='Настройка этапов отбора', 
                         stages=stages,
                         form=form)

# API для работы с этапами отбора
@settings_bp.route('/api/selection-stages', methods=['GET'])
@login_required
@hr_required
def api_get_selection_stages():
    """Получение списка этапов отбора в формате JSON"""
    # Получаем этапы отбора текущего пользователя или стандартные, если нет собственных
    stages = current_user.get_selection_stages()
    
    return jsonify([{
        'id': stage.id,
        'name': stage.name,
        'description': stage.description,
        'color': stage.color,
        'order': stage.order,
        'is_active': stage.is_active,
        'is_standard': stage.is_standard
    } for stage in stages])

@settings_bp.route('/api/reset-selection-stages', methods=['POST'])
@login_required
@hr_required
def api_reset_selection_stages():
    """Сброс этапов отбора на стандартные"""
    try:
        # Удаляем существующие связи пользователя с этапами отбора
        User_Selection_Stage.query.filter_by(user_id=current_user.id).delete()
        
        # Загружаем стандартные этапы
        default_stages = C_Selection_Stage.query.filter_by(is_standard=True).order_by(C_Selection_Stage.order).all()
        
        # Создаем новые связи для стандартных этапов
        for i, stage in enumerate(default_stages):
            user_stage = User_Selection_Stage(
                user_id=current_user.id,
                stage_id=stage.id,
                order=i + 1,
                is_active=True
            )
            db.session.add(user_stage)
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Этапы отбора сброшены на стандартные'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка при сбросе этапов отбора: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@settings_bp.route('/api/selection-stages/<int:stage_id>', methods=['DELETE'])
@login_required
@hr_required
def api_delete_selection_stage(stage_id):
    """Удаление этапа отбора из списка пользователя"""
    try:
        # Проверяем существование связи
        user_stage = User_Selection_Stage.query.filter_by(
            user_id=current_user.id,
            stage_id=stage_id
        ).first_or_404()
        
        # Удаляем связь
        db.session.delete(user_stage)
        db.session.commit()
        
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка при удалении этапа отбора: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500 
    