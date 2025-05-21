#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.c_selection_stage import C_Selection_Stage
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
    
    if request.method == 'POST':
        try:
            # Получаем данные о этапах отбора из формы
            stages_data = json.loads(request.form.get('stages_data', '[]'))
            
            # Очищаем существующие связи пользователя с этапами отбора
            current_user.selection_stages = []
            
            # Создаем новые этапы или связываем с существующими
            for i, stage_data in enumerate(stages_data):
                stage_id = stage_data.get('id')
                
                if stage_id:
                    # Проверяем, существует ли этап с таким ID
                    stage = C_Selection_Stage.query.get(stage_id)
                    if not stage:
                        # Если нет, создаем новый
                        stage = C_Selection_Stage(
                            name=stage_data['name'],
                            description=stage_data.get('description', ''),
                            color=stage_data.get('color', '#6c757d'),
                            order=i + 1,
                            is_active=stage_data.get('is_active', True),
                            is_default=False
                        )
                        db.session.add(stage)
                    else:
                        # Если этап стандартный (is_default=True), создаем его копию
                        if stage.is_default:
                            new_stage = C_Selection_Stage(
                                name=stage_data['name'],
                                description=stage_data.get('description', ''),
                                color=stage_data.get('color', '#6c757d'),
                                order=i + 1,
                                is_active=stage_data.get('is_active', True),
                                is_default=False
                            )
                            db.session.add(new_stage)
                            stage = new_stage
                else:
                    # Создаем новый этап
                    stage = C_Selection_Stage(
                        name=stage_data['name'],
                        description=stage_data.get('description', ''),
                        color=stage_data.get('color', '#6c757d'),
                        order=i + 1,
                        is_active=stage_data.get('is_active', True),
                        is_default=False
                    )
                    db.session.add(stage)
                
                # Добавляем этап к пользователю
                current_user.selection_stages.append(stage)
                
            # Сохраняем изменения
            db.session.commit()
            flash('Этапы отбора успешно обновлены!', 'success')
            return redirect(url_for('settings_bp.selection_stages'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Ошибка при обновлении этапов отбора: {str(e)}")
            flash('Произошла ошибка при обновлении этапов отбора.', 'danger')
    
    return render_template('settings/selection_stages.html', title='Настройка этапов отбора', stages=stages)

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
        'is_default': stage.is_default
    } for stage in stages])

@settings_bp.route('/api/reset-selection-stages', methods=['POST'])
@login_required
@hr_required
def api_reset_selection_stages():
    """Сброс этапов отбора на стандартные"""
    try:
        # Очищаем существующие этапы пользователя
        current_user.selection_stages = []
        
        # Загружаем стандартные этапы
        default_stages = C_Selection_Stage.query.filter_by(is_default=True).order_by(C_Selection_Stage.order).all()
        
        # Устанавливаем стандартные этапы для текущего пользователя
        current_user.selection_stages = default_stages
        
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
        stage = C_Selection_Stage.query.get_or_404(stage_id)
        
        # Если этап стандартный, просто удаляем связь с пользователем
        if stage.is_default:
            if stage in current_user.selection_stages:
                current_user.selection_stages.remove(stage)
        else:
            # Проверяем, принадлежит ли этап текущему пользователю
            if stage in current_user.selection_stages:
                current_user.selection_stages.remove(stage)
                # Удаляем этап, если он не используется другими пользователями
                if not stage.users:
                    db.session.delete(stage)
        
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка при удалении этапа отбора: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500 
    