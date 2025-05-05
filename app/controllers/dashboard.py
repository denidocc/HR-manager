#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Vacancy, Candidate, C_Candidate_Status, Notification, SystemLog, User, C_User_Status
from app.controllers.auth import admin_required
from sqlalchemy import func, desc, and_, cast
import datetime
import sqlalchemy as sa
from flask import current_app

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
@admin_required
def index():
    """Главная страница дашборда"""
    # Статистика по системе
    active_vacancies_count = Vacancy.query.filter_by(is_active=True).count()
    total_candidates_count = Candidate.query.count()
    recent_candidates_count = Candidate.query.filter(
        Candidate.created_at >= datetime.datetime.now() - datetime.timedelta(days=7)
    ).count()
    
    # Статусы кандидатов
    candidate_statuses_counts = {}
    statuses = C_Candidate_Status.query.all()
    for status in statuses:
        count = Candidate.query.filter_by(id_c_candidate_status=status.id).count()
        candidate_statuses_counts[status.name] = {
            'count': count, 
            'color': status.color_code
        }
    
    # Последние кандидаты
    recent_candidates = Candidate.query.order_by(Candidate.created_at.desc()).limit(5).all()
    
    # Вакансии с наибольшим количеством кандидатов
    top_vacancies = db.session.query(
        Vacancy.id, Vacancy.title, func.count(Candidate.id).label('candidates_count')
    ).join(Candidate, Vacancy.id == Candidate.vacancy_id)\
     .group_by(Vacancy.id)\
     .order_by(desc('candidates_count'))\
     .limit(5).all()
    
    # Последние события системы
    recent_logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(10).all()
    
    # Пользователи с высоким рейтингом AI
    top_candidates = Candidate.query.filter(Candidate.ai_match_percent != None)\
        .order_by(Candidate.ai_match_percent.desc())\
        .limit(5).all()
    
    # Ближайшие интервью
    upcoming_interviews = Candidate.query.filter(
        and_(
            Candidate.interview_date != None,
            Candidate.interview_date >= datetime.datetime.now(),
            Candidate.id_c_candidate_status == 1  # ID статуса "Назначено интервью"
        )
    ).order_by(Candidate.interview_date).all()
    
    return render_template(
        'dashboard/index.html',
        active_vacancies_count=active_vacancies_count,
        total_candidates_count=total_candidates_count,
        recent_candidates_count=recent_candidates_count,
        candidate_statuses_counts=candidate_statuses_counts,
        recent_candidates=recent_candidates,
        top_vacancies=top_vacancies,
        recent_logs=recent_logs,
        top_candidates=top_candidates,
        upcoming_interviews=upcoming_interviews,
        title='Панель управления'
    )

@dashboard_bp.route('/statistics')
@login_required
@admin_required
def statistics():
    """Страница с подробной статистикой"""
    # Данные по количеству кандидатов по датам
    dates = db.session.query(
        func.date_trunc('day', Candidate.created_at).label('date'),
        func.count(Candidate.id).label('count')
    ).group_by('date').order_by('date').all()
    
    dates_data = [
        {'date': date.strftime('%Y-%m-%d'), 'count': count}
        for date, count in dates
    ]
    
    # Данные по вакансиям и статусам кандидатов
    vacancies = Vacancy.query.all()
    statuses = C_Candidate_Status.query.all()
    
    vacancy_status_data = []
    for vacancy in vacancies:
        vacancy_data = {'name': vacancy.title, 'data': []}
        for status in statuses:
            count = Candidate.query.filter_by(
                vacancy_id=vacancy.id, 
                id_c_candidate_status=status.id
            ).count()
            vacancy_data['data'].append({
                'status': status.name,
                'count': count,
                'color': status.color_code
            })
        vacancy_status_data.append(vacancy_data)
    
    # Средний процент совпадения кандидатов по AI
    avg_match = db.session.query(
        func.avg(Candidate.ai_match_percent)
    ).filter(Candidate.ai_match_percent != None).scalar() or 0
    
    return render_template(
        'dashboard/statistics.html',
        dates_data=dates_data,
        vacancy_status_data=vacancy_status_data,
        avg_match=avg_match,
        statuses=statuses,
        title='Статистика'
    )

@dashboard_bp.route('/api/chart_data')
@login_required
@admin_required
def api_chart_data():
    """API для получения данных для графиков"""
    # Статистика по кандидатам по дням
    last_30_days = datetime.datetime.now() - datetime.timedelta(days=30)
    
    candidates_by_day = db.session.query(
        func.date_trunc('day', Candidate.created_at).label('date'),
        func.count(Candidate.id).label('count')
    ).filter(Candidate.created_at >= last_30_days)\
     .group_by('date')\
     .order_by('date').all()
    
    # Преобразование в формат для Chart.js
    dates = [date.strftime('%Y-%m-%d') for date, _ in candidates_by_day]
    counts = [count for _, count in candidates_by_day]
    
    # Распределение кандидатов по статусам
    status_data = db.session.query(
        C_Candidate_Status.name,
        C_Candidate_Status.color_code,
        func.count(Candidate.id).label('count')
    ).join(Candidate, C_Candidate_Status.id == Candidate.id_c_candidate_status)\
     .group_by(C_Candidate_Status.id)\
     .order_by(desc('count')).all()
    
    status_labels = [status for status, _, _ in status_data]
    status_counts = [count for _, _, count in status_data]
    status_colors = [color for _, color, _ in status_data]
    
    return jsonify({
        'candidates_by_day': {
            'labels': dates,
            'datasets': [{
                'label': 'Новые кандидаты',
                'data': counts,
                'borderColor': '#6290C3',
                'backgroundColor': 'rgba(98, 144, 195, 0.2)'
            }]
        },
        'candidates_by_status': {
            'labels': status_labels,
            'datasets': [{
                'data': status_counts,
                'backgroundColor': status_colors
            }]
        }
    })

@dashboard_bp.route('/users')
@login_required
@admin_required
def users():
    """Страница управления пользователями (только для администраторов)"""
    # Получаем параметры фильтрации и пагинации
    user_status_id = request.args.get('status', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Загружаем все статусы пользователей для фильтрации
    statuses = C_User_Status.query.all()
    
    # Создаем базовый запрос с дешифрованием полей
    base_query = db.session.query(
        User.id,
        User.full_name,
        User._email.label('email_encrypted'),
        User._phone.label('phone_encrypted'),
        User.role,
        User.company,
        User.position,
        User.id_c_user_status,
        User.created_at,
        C_User_Status.name.label('status_name')
    ).join(
        C_User_Status, User.id_c_user_status == C_User_Status.id
    )
    
    # Применяем фильтр по статусу, если указан
    if user_status_id:
        base_query = base_query.filter(User.id_c_user_status == user_status_id)
    
    # Сортировка по дате создания (от новых к старым)
    base_query = base_query.order_by(User.created_at.desc())
    
    # Получаем общее количество записей
    total_items = base_query.count()
    total_pages = (total_items + per_page - 1) // per_page  # округление вверх
    
    # Применяем пагинацию
    users_subquery = base_query.limit(per_page).offset((page - 1) * per_page).subquery()
    
    # Получаем результаты с дешифровкой
    db_users = db.session.query(
        users_subquery.c.id,
        users_subquery.c.full_name,
        func.pgp_sym_decrypt(
            cast(users_subquery.c.email_encrypted, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('email'),
        func.pgp_sym_decrypt(
            cast(users_subquery.c.phone_encrypted, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('phone'),
        users_subquery.c.role,
        users_subquery.c.company,
        users_subquery.c.position,
        users_subquery.c.id_c_user_status,
        users_subquery.c.created_at,
        users_subquery.c.status_name
    ).all()
    
    # Преобразуем результаты в список словарей для шаблона
    users = [{
        'id': user.id,
        'full_name': user.full_name,
        'email': user.email,
        'phone': user.phone,
        'role': user.role,
        'company': user.company,
        'position': user.position,
        'id_c_user_status': user.id_c_user_status,
        'created_at': user.created_at.strftime('%d.%m.%Y %H:%M'),
        'status_name': user.status_name
    } for user in db_users]
    
    # Информация о пагинации
    pagination = {
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total_items,
        "per_page": per_page
    }
    
    return render_template(
        'dashboard/users.html',
        users=users,
        statuses=statuses,
        current_status=user_status_id,
        pagination=pagination
    )

@dashboard_bp.route('/approve-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    """Подтверждение заявки на регистрацию HR-менеджера"""
    user = User.query.get_or_404(user_id)
    
    # Проверяем, что пользователь в статусе "Ожидает подтверждения"
    if user.id_c_user_status != 2:  # Статус "Ожидает подтверждения"
        flash('Пользователь не нуждается в подтверждении или уже подтвержден', 'warning')
        return redirect(url_for('dashboard.users'))
    
    # Меняем статус на "Активен"
    user.id_c_user_status = 1  # Статус "Активен"
    
    # Логирование действия
    log = SystemLog(
        event_type='approve_user',
        description=f'Подтверждение регистрации пользователя {user.full_name}',
        ip_address=request.remote_addr,
        user_id=current_user.id
    )
    
    db.session.add(log)
    db.session.commit()
    
    flash('Пользователь успешно подтвержден', 'success')
    return redirect(url_for('dashboard.users'))

@dashboard_bp.route('/reject-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reject_user(user_id):
    """Отклонение заявки на регистрацию HR-менеджера"""
    user = User.query.get_or_404(user_id)
    
    # Проверяем, что пользователь в статусе "Ожидает подтверждения"
    if user.id_c_user_status != 2:  # Статус "Ожидает подтверждения"
        flash('Пользователь не нуждается в подтверждении или уже обработан', 'warning')
        return redirect(url_for('dashboard.users'))
    
    # Меняем статус на "Отклонен"
    user.id_c_user_status = 3  # Статус "Отклонен"
    
    # Логирование действия
    log = SystemLog(
        event_type='reject_user',
        description=f'Отклонение регистрации пользователя {user.full_name}',
        ip_address=request.remote_addr,
        user_id=current_user.id
    )
    
    db.session.add(log)
    db.session.commit()
    
    flash('Регистрация пользователя отклонена', 'success')
    return redirect(url_for('dashboard.users'))

@dashboard_bp.route('/hr')
@login_required
def hr_dashboard():
    """Главная страница дашборда для HR-менеджеров"""
    # Статистика по системе (упрощенная для HR)
    
    # Получаем только вакансии текущего HR-менеджера
    my_vacancies = Vacancy.query.filter_by(created_by=current_user.id).all()
    my_vacancy_ids = [vacancy.id for vacancy in my_vacancies]
    
    # Общее количество вакансий HR-менеджера
    total_my_vacancies_count = len(my_vacancies)
    
    # Статистика активных вакансий HR-менеджера
    active_vacancies_count = Vacancy.query.filter_by(is_active=True, created_by=current_user.id).count()
    
    # Общее количество кандидатов на вакансии HR-менеджера
    total_candidates_count = Candidate.query.filter(Candidate.vacancy_id.in_(my_vacancy_ids)).count() if my_vacancy_ids else 0
    
    # Последние кандидаты только на вакансии текущего HR-менеджера
    recent_candidates = Candidate.query.filter(Candidate.vacancy_id.in_(my_vacancy_ids)).order_by(Candidate.created_at.desc()).limit(5).all() if my_vacancy_ids else []
    
    # Вакансии HR-менеджера с наибольшим количеством кандидатов
    top_vacancies = db.session.query(
        Vacancy.id, Vacancy.title, func.count(Candidate.id).label('candidates_count')
    ).join(Candidate, Vacancy.id == Candidate.vacancy_id)\
     .filter(Vacancy.created_by == current_user.id)\
     .group_by(Vacancy.id)\
     .order_by(desc('candidates_count'))\
     .limit(5).all()
    
    return render_template(
        'dashboard/hr_dashboard.html',
        active_vacancies_count=active_vacancies_count,
        total_candidates_count=total_candidates_count,
        recent_candidates=recent_candidates,
        top_vacancies=top_vacancies,
        total_my_vacancies_count=total_my_vacancies_count,
        title='HR Панель управления'
    ) 