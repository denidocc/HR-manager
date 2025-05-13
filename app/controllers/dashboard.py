#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db, cache
from app.models import Vacancy, Candidate, C_Candidate_Status, Notification, SystemLog, User, C_User_Status, Skill, SkillCategory, CandidateSkill, VacancySkill, Industry, VacancyIndustry
from app.controllers.auth import admin_required, hr_required
from sqlalchemy import func, desc, and_, cast, case
import datetime
import sqlalchemy as sa
from flask import current_app
import pandas as pd
import re
from collections import Counter
from app.utils.decorators import profile_time

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@profile_time
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
            Candidate.id_c_candidate_status == 2  # ID статуса "Назначено интервью"
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
@profile_time
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
@profile_time
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
@profile_time
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
@profile_time
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
@profile_time
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
@profile_time
@login_required
@hr_required
def hr_dashboard():
    """Главная страница дашборда для HR-менеджеров"""
    # Получаем только вакансии текущего HR-менеджера
    my_vacancy_ids = db.session.query(Vacancy.id).filter_by(created_by=current_user.id).all()
    my_vacancy_ids = [v[0] for v in my_vacancy_ids]
    
    # Оптимизированные запросы с использованием подзапросов
    active_vacancies_count = db.session.query(func.count(Vacancy.id))\
        .filter(Vacancy.is_active == True, Vacancy.created_by == current_user.id)\
        .scalar()
    
    total_candidates_count = db.session.query(func.count(Candidate.id))\
        .filter(Candidate.vacancy_id.in_(my_vacancy_ids))\
        .scalar() if my_vacancy_ids else 0
    
    # Последние кандидаты с оптимизированным запросом
    recent_candidates = db.session.query(Candidate)\
        .filter(Candidate.vacancy_id.in_(my_vacancy_ids))\
        .order_by(Candidate.created_at.desc())\
        .limit(5).all() if my_vacancy_ids else []
    
    # Топ вакансий с оптимизированным запросом
    top_vacancies = db.session.query(
        Vacancy.id, Vacancy.title, func.count(Candidate.id).label('candidates_count')
    ).join(Candidate, Vacancy.id == Candidate.vacancy_id)\
     .filter(Vacancy.created_by == current_user.id)\
     .group_by(Vacancy.id, Vacancy.title)\
     .order_by(desc('candidates_count'))\
     .limit(5).all()
    
    return render_template(
        'dashboard/hr_dashboard.html',
        active_vacancies_count=active_vacancies_count,
        total_candidates_count=total_candidates_count,
        recent_candidates=recent_candidates,
        top_vacancies=top_vacancies,
        total_my_vacancies_count=len(my_vacancy_ids),
        title='HR Панель управления'
    )

@dashboard_bp.route('/statistics/recruitment_funnel')
@profile_time
@login_required
@hr_required
def recruitment_funnel():
    """Страница с воронкой найма"""
    # Получаем данные по этапам воронки для каждой вакансии
    vacancy_id = request.args.get('vacancy_id', type=int)
    
    # Базовый запрос
    query = db.session.query(
        Vacancy.id,
        Vacancy.title,
        func.count(Candidate.id).label('total_applications'),
        func.sum(case([(Candidate.id_c_candidate_status == 0, 1)], else_=0)).label('new_applications'),
        func.sum(case([(Candidate.id_c_candidate_status == 1, 1)], else_=0)).label('reviewed'),
        func.sum(case([(Candidate.id_c_candidate_status == 2, 1)], else_=0)).label('interview_invited'),
        func.sum(case([(Candidate.id_c_candidate_status == 5, 1)], else_=0)).label('interviewed'),
        func.sum(case([(Candidate.id_c_candidate_status == 4, 1)], else_=0)).label('offered'),
        func.sum(case([(Candidate.id_c_candidate_status == 3, 1)], else_=0)).label('hired')
    ).join(
        Candidate, Vacancy.id == Candidate.vacancy_id
    )
    
    # Фильтрация по конкретной вакансии если указана
    if vacancy_id:
        query = query.filter(Vacancy.id == vacancy_id)
    
    # Группировка и выполнение
    funnel_data = query.group_by(Vacancy.id).all()
    
    # Преобразование для фронтенда
    vacancies = []
    for data in funnel_data:
        vacancy = {
            'id': data.id,
            'title': data.title,
            'funnel': [
                {'stage': 'Всего заявок', 'count': data.total_applications},
                {'stage': 'Новые заявки', 'count': data.new_applications},
                {'stage': 'Рассмотрено', 'count': data.reviewed},
                {'stage': 'Приглашено', 'count': data.interview_invited},
                {'stage': 'Интервью проведено', 'count': data.interviewed},
                {'stage': 'Предложение', 'count': data.offered},
                {'stage': 'Трудоустроено', 'count': data.hired}
            ]
        }
        vacancies.append(vacancy)
    
    return render_template(
        'dashboard/statistics/recruitment_funnel.html',
        vacancies=vacancies,
        title='Воронка найма'
    )

@dashboard_bp.route('/statistics/time_to_fill')
@profile_time
@login_required
@hr_required
def time_to_fill():
    """Страница с анализом времени закрытия вакансий"""
    # Получаем данные о времени закрытия вакансий
    time_data = db.session.query(
        Vacancy.id,
        Vacancy.title,
        Vacancy.created_at,
        Vacancy.closed_at,
        func.extract('day', Vacancy.closed_at - Vacancy.created_at).label('days_to_fill')
    ).filter(
        Vacancy.closed_at != None
    ).order_by(Vacancy.closed_at.desc()).all()
    
    # Расчет средних показателей с помощью pandas
    df = pd.DataFrame([
        {
            'id': v.id,
            'title': v.title,
            'created_at': v.created_at,
            'closed_at': v.closed_at,
            'days_to_fill': v.days_to_fill
        } for v in time_data
    ])
    
    # Расчет статистики
    if not df.empty:
        avg_time = df['days_to_fill'].mean()
        median_time = df['days_to_fill'].median()
        # Тренд по месяцам
        df['month'] = df['closed_at'].apply(lambda x: x.strftime('%Y-%m'))
        monthly_avg = df.groupby('month')['days_to_fill'].mean().reset_index()
        monthly_data = monthly_avg.to_dict('records')
    else:
        avg_time = 0
        median_time = 0
        monthly_data = []
    
    return render_template(
        'dashboard/statistics/time_to_fill.html',
        time_data=time_data,
        avg_time=avg_time,
        median_time=median_time,
        monthly_data=monthly_data,
        title='Время закрытия вакансий'
    )

@dashboard_bp.route('/skills_analysis')
@profile_time
@login_required
@hr_required
def skills_analysis():
    """Анализ навыков кандидатов по всем отраслям на основе моделей в базе данных"""
    try:
        # Получаем все категории навыков
        skill_categories = db.session.query(
            SkillCategory.id,
            SkillCategory.name
        ).filter(SkillCategory.is_active == True).all()
        
        # Получаем статистику по навыкам кандидатов
        candidate_skills_stats = db.session.query(
            Skill.id,
            Skill.name,
            Skill.category_id,
            SkillCategory.name.label('category_name'),
            func.count(CandidateSkill.id).label('candidate_count'),
            func.avg(CandidateSkill.level).label('avg_level'),
            func.avg(CandidateSkill.experience_months).label('avg_experience_months')
        ).join(
            CandidateSkill, Skill.id == CandidateSkill.skill_id
        ).join(
            SkillCategory, Skill.category_id == SkillCategory.id
        ).group_by(
            Skill.id, SkillCategory.name
        ).order_by(
            func.count(CandidateSkill.id).desc()
        ).limit(50).all()
        
        # Получаем статистику по навыкам вакансий
        vacancy_skills_stats = db.session.query(
            Skill.id,
            Skill.name,
            Skill.category_id,
            SkillCategory.name.label('category_name'),
            func.count(VacancySkill.id).label('vacancy_count'),
            func.avg(VacancySkill.importance).label('avg_importance'),
            func.sum(case([(VacancySkill.is_required == True, 1)], else_=0)).label('required_count')
        ).join(
            VacancySkill, Skill.id == VacancySkill.skill_id
        ).join(
            SkillCategory, Skill.category_id == SkillCategory.id
        ).group_by(
            Skill.id, SkillCategory.name
        ).order_by(
            func.count(VacancySkill.id).desc()
        ).limit(50).all()
        
        # Объединяем данные и преобразуем в DataFrame для анализа
        skills_data = []
        for skill in candidate_skills_stats:
            # Ищем этот навык в вакансиях
            vacancy_data = next((v for v in vacancy_skills_stats if v.id == skill.id), None)
            
            skills_data.append({
                'id': skill.id,
                'name': skill.name,
                'category_id': skill.category_id,
                'category_name': skill.category_name,
                'candidate_count': skill.candidate_count,
                'avg_level': round(skill.avg_level, 1) if skill.avg_level else 0,
                'avg_experience_months': round(skill.avg_experience_months, 1) if skill.avg_experience_months else 0,
                'vacancy_count': vacancy_data.vacancy_count if vacancy_data else 0,
                'avg_importance': round(vacancy_data.avg_importance, 1) if vacancy_data and vacancy_data.avg_importance else 0,
                'required_count': vacancy_data.required_count if vacancy_data else 0,
                'demand_supply_ratio': round(vacancy_data.vacancy_count / skill.candidate_count, 2) if vacancy_data and skill.candidate_count > 0 else 0
            })
        
        # Навыки, которые есть в вакансиях, но не встречаются у кандидатов
        for skill in vacancy_skills_stats:
            if not any(s['id'] == skill.id for s in skills_data):
                skills_data.append({
                    'id': skill.id,
                    'name': skill.name,
                    'category_id': skill.category_id,
                    'category_name': skill.category_name,
                    'candidate_count': 0,
                    'avg_level': 0,
                    'avg_experience_months': 0,
                    'vacancy_count': skill.vacancy_count,
                    'avg_importance': round(skill.avg_importance, 1) if skill.avg_importance else 0,
                    'required_count': skill.required_count,
                    'demand_supply_ratio': float('inf')  # Бесконечно высокий спрос
                })
        
        # Анализ по категориям навыков
        category_data = {}
        for category in skill_categories:
            category_skills = [s for s in skills_data if s['category_id'] == category.id]
            
            if category_skills:
                avg_demand_supply = sum(s['demand_supply_ratio'] for s in category_skills if s['demand_supply_ratio'] != float('inf')) / len([s for s in category_skills if s['demand_supply_ratio'] != float('inf') and s['demand_supply_ratio'] > 0]) if any(s['demand_supply_ratio'] != float('inf') and s['demand_supply_ratio'] > 0 for s in category_skills) else 0
                
                category_data[category.id] = {
                    'name': category.name,
                    'skill_count': len(category_skills),
                    'avg_demand_supply': round(avg_demand_supply, 2),
                    'top_skills': sorted(category_skills, key=lambda x: x['vacancy_count'], reverse=True)[:5],
                    'gap_skills': sorted([s for s in category_skills if s['demand_supply_ratio'] > 1.5], key=lambda x: x['demand_supply_ratio'], reverse=True)[:5]
                }
        
        # Получаем данные по отраслям
        industry_data = db.session.query(
            Industry.id,
            Industry.name,
            func.count(VacancyIndustry.vacancy_id).label('vacancy_count')
        ).join(
            VacancyIndustry, Industry.id == VacancyIndustry.industry_id
        ).group_by(
            Industry.id
        ).order_by(
            func.count(VacancyIndustry.vacancy_id).desc()
        ).limit(10).all()
        
        # Преобразуем для шаблона
        industries = [{'id': i.id, 'name': i.name, 'vacancy_count': i.vacancy_count} for i in industry_data]
        
        # Сортируем навыки для отображения
        # 1. Самые популярные навыки по количеству вакансий
        top_demanded_skills = sorted(skills_data, key=lambda x: x['vacancy_count'], reverse=True)[:20]
        
        # 2. Навыки с наибольшим разрывом спроса/предложения
        skill_gaps = sorted([s for s in skills_data if s['demand_supply_ratio'] != float('inf')], 
                           key=lambda x: x['demand_supply_ratio'], reverse=True)[:20]
        
        # 3. Навыки с высоким средним уровнем важности
        important_skills = sorted(skills_data, key=lambda x: x['avg_importance'], reverse=True)[:20]
        
        return render_template(
            'dashboard/statistics/skills_analysis.html',
            skills_data=skills_data,
            top_demanded_skills=top_demanded_skills,
            skill_gaps=skill_gaps,
            important_skills=important_skills,
            category_data=category_data,
            industries=industries,
            title='Анализ навыков кандидатов'
        )
    except Exception as e:
        current_app.logger.error(f"Ошибка при анализе навыков: {str(e)}")
        flash(f"Ошибка при анализе навыков: {str(e)}", "danger")
        return redirect(url_for('dashboard.statistics'))

@dashboard_bp.route('/statistics/source_analysis')
@profile_time
@login_required
@hr_required
def source_analysis():
    """Страница с анализом источников кандидатов"""
    try:
        # Получаем данные о кандидатах и их источниках
        candidates = db.session.query(
            Candidate.source,
            func.count(Candidate.id).label('count'),
            func.sum(case([(Candidate.status_id == 6, 1)], else_=0)).label('hired_count')
        ).group_by(Candidate.source).all()
        
        # Преобразуем в DataFrame для удобства анализа
        df = pd.DataFrame([(c.source, c.count, c.hired_count) for c in candidates], 
                          columns=['source', 'total_count', 'hired_count'])
        
        # Добавляем конверсию
        df['conversion'] = (df['hired_count'] / df['total_count'] * 100).round(1)
        
        # Рассчитываем примерную стоимость найма
        # Предполагаем, что у нас есть данные о стоимости каждого источника
        source_costs = {
            'HH.ru': 15000,
            'Хабр Карьера': 10000,
            'LinkedIn': 20000,
            'Рекомендация': 5000,
            'Сайт компании': 2000,
            'Другое': 5000
        }
        
        # Добавляем стоимость для каждого источника
        df['cost'] = df['source'].map(lambda x: source_costs.get(x, 5000))
        
        # Рассчитываем стоимость найма одного сотрудника (Cost per Hire)
        df['cost_per_hire'] = (df['cost'] / df['hired_count']).fillna(0).round(0)
        
        # Рассчитываем ROI
        df['roi'] = ((df['hired_count'] * 100000 - df['cost']) / df['cost'] * 100).fillna(0).round(1)
        
        # Преобразуем в список словарей для передачи в шаблон
        sources_data = df.to_dict('records')
        
        # Получаем данные для графиков
        chart_data = {
            'labels': df['source'].tolist(),
            'total_counts': df['total_count'].tolist(),
            'hired_counts': df['hired_count'].tolist(),
            'conversion_rates': df['conversion'].tolist(),
            'cost_per_hire': df['cost_per_hire'].tolist(),
            'roi': df['roi'].tolist()
        }
        
        return render_template(
            'dashboard/statistics/source_analysis.html',
            sources_data=sources_data,
            chart_data=chart_data
        )
    except Exception as e:
        current_app.logger.error(f"Ошибка при анализе источников кандидатов: {str(e)}")
        flash(f"Ошибка при анализе источников кандидатов: {str(e)}", "danger")
        return redirect(url_for('dashboard.statistics'))

@dashboard_bp.route('/statistics/qualification_analysis')
@profile_time
@login_required
@hr_required
def qualification_analysis():
    """Страница с анализом квалификации кандидатов на основе данных из базы"""
    try:
        # Получаем все вакансии с их индустриями
        vacancies_with_industries = db.session.query(
            Vacancy.id,
            Vacancy.title,
            Industry.name.label('industry_name')
        ).join(
            VacancyIndustry, Vacancy.id == VacancyIndustry.vacancy_id
        ).join(
            Industry, VacancyIndustry.industry_id == Industry.id
        ).all()
        
        # Создаем словарь вакансий с индустриями
        vacancy_industries = {}
        for v in vacancies_with_industries:
            if v.id not in vacancy_industries:
                vacancy_industries[v.id] = {
                    'title': v.title,
                    'industries': []
                }
            vacancy_industries[v.id]['industries'].append(v.industry_name)
        
        # Получаем все индустрии для фильтрации
        industries = db.session.query(
            Industry.id,
            Industry.name,
            func.count(VacancyIndustry.vacancy_id).label('vacancy_count')
        ).join(
            VacancyIndustry, Industry.id == VacancyIndustry.industry_id
        ).group_by(Industry.id).all()
        
        # Получаем данные о кандидатах с их оценками AI и навыками
        candidates = db.session.query(
            Candidate.id,
            Candidate.full_name,
            Candidate.vacancy_id,
            Candidate.ai_match_percent,
            Candidate.ai_score_tech,
            Candidate.ai_score_experience,
            Candidate.ai_score_education,
            Vacancy.title.label('vacancy_title')
        ).join(
            Vacancy, Candidate.vacancy_id == Vacancy.id
        ).filter(
            Candidate.ai_match_percent.isnot(None)
        ).all()
        
        # Получаем навыки кандидатов
        candidate_skills = db.session.query(
            CandidateSkill.candidate_id,
            CandidateSkill.skill_id,
            CandidateSkill.level,
            Skill.name.label('skill_name'),
            SkillCategory.name.label('category_name')
        ).join(
            Skill, CandidateSkill.skill_id == Skill.id
        ).join(
            SkillCategory, Skill.category_id == SkillCategory.id
        ).all()
        
        # Создаем словарь навыков по кандидатам
        candidate_skills_dict = {}
        for cs in candidate_skills:
            if cs.candidate_id not in candidate_skills_dict:
                candidate_skills_dict[cs.candidate_id] = []
            
            candidate_skills_dict[cs.candidate_id].append({
                'name': cs.skill_name,
                'level': cs.level,
                'category': cs.category_name
            })
        
        # Преобразуем в DataFrame для удобства анализа
        candidates_data = []
        for c in candidates:
            # Получаем индустрии вакансии
            industries_list = vacancy_industries.get(c.vacancy_id, {}).get('industries', [])
            
            # Получаем навыки кандидата
            skills = candidate_skills_dict.get(c.id, [])
            
            candidates_data.append({
                'id': c.id,
                'full_name': c.full_name,
                'vacancy_id': c.vacancy_id,
                'vacancy_title': c.vacancy_title,
                'industries': industries_list,
                'match_percent': c.ai_match_percent,
                'tech_score': c.ai_score_tech,
                'experience_score': c.ai_score_experience,
                'education_score': c.ai_score_education,
                'skills': skills,
                'skill_count': len(skills),
                'avg_skill_level': round(sum(s['level'] for s in skills) / len(skills), 1) if skills else 0
            })
        
        # Анализ по индустриям
        industry_analysis = {}
        for industry in industries:
            # Находим кандидатов в этой индустрии
            industry_candidates = [c for c in candidates_data if industry.name in c['industries']]
            
            if industry_candidates:
                avg_match = sum(c['match_percent'] for c in industry_candidates) / len(industry_candidates) if industry_candidates else 0
                avg_tech = sum(c['tech_score'] for c in industry_candidates if c['tech_score']) / len([c for c in industry_candidates if c['tech_score']]) if any(c['tech_score'] for c in industry_candidates) else 0
                avg_exp = sum(c['experience_score'] for c in industry_candidates if c['experience_score']) / len([c for c in industry_candidates if c['experience_score']]) if any(c['experience_score'] for c in industry_candidates) else 0
                avg_edu = sum(c['education_score'] for c in industry_candidates if c['education_score']) / len([c for c in industry_candidates if c['education_score']]) if any(c['education_score'] for c in industry_candidates) else 0
                
                # Собираем все навыки кандидатов в этой индустрии
                all_skills = []
                for c in industry_candidates:
                    all_skills.extend(c['skills'])
                
                # Считаем частоту навыков
                skill_frequency = {}
                for skill in all_skills:
                    if skill['name'] not in skill_frequency:
                        skill_frequency[skill['name']] = {
                            'count': 0,
                            'category': skill['category'],
                            'total_level': 0
                        }
                    skill_frequency[skill['name']]['count'] += 1
                    skill_frequency[skill['name']]['total_level'] += skill['level']
                
                # Преобразуем в список и сортируем по частоте
                top_skills = [
                    {
                        'name': name,
                        'count': data['count'],
                        'category': data['category'],
                        'avg_level': round(data['total_level'] / data['count'], 1)
                    }
                    for name, data in skill_frequency.items()
                ]
                top_skills.sort(key=lambda x: x['count'], reverse=True)
                
                industry_analysis[industry.id] = {
                    'name': industry.name,
                    'candidate_count': len(industry_candidates),
                    'vacancy_count': industry.vacancy_count,
                    'avg_match_percent': round(avg_match, 1),
                    'avg_tech_score': round(avg_tech, 1),
                    'avg_experience_score': round(avg_exp, 1),
                    'avg_education_score': round(avg_edu, 1),
                    'top_skills': top_skills[:10]
                }
        
        # Группируем кандидатов по вакансиям для анализа
        vacancies_data = {}
        for c in candidates_data:
            if c['vacancy_id'] not in vacancies_data:
                vacancies_data[c['vacancy_id']] = {
                    'id': c['vacancy_id'],
                    'title': c['vacancy_title'],
                    'industries': c['industries'],
                    'candidates': [],
                    'candidate_count': 0,
                    'avg_match': 0,
                    'min_match': 100,
                    'max_match': 0,
                    'avg_tech': 0,
                    'avg_experience': 0,
                    'avg_education': 0
                }
            
            vacancies_data[c['vacancy_id']]['candidates'].append(c)
            vacancies_data[c['vacancy_id']]['candidate_count'] += 1
            vacancies_data[c['vacancy_id']]['avg_match'] += c['match_percent'] or 0
            vacancies_data[c['vacancy_id']]['min_match'] = min(vacancies_data[c['vacancy_id']]['min_match'], c['match_percent'] or 100)
            vacancies_data[c['vacancy_id']]['max_match'] = max(vacancies_data[c['vacancy_id']]['max_match'], c['match_percent'] or 0)
            vacancies_data[c['vacancy_id']]['avg_tech'] += c['tech_score'] or 0
            vacancies_data[c['vacancy_id']]['avg_experience'] += c['experience_score'] or 0
            vacancies_data[c['vacancy_id']]['avg_education'] += c['education_score'] or 0
        
        # Рассчитываем средние значения
        for vacancy_id, data in vacancies_data.items():
            data['avg_match'] = round(data['avg_match'] / data['candidate_count'], 1) if data['candidate_count'] > 0 else 0
            data['avg_tech'] = round(data['avg_tech'] / data['candidate_count'], 1) if data['candidate_count'] > 0 else 0
            data['avg_experience'] = round(data['avg_experience'] / data['candidate_count'], 1) if data['candidate_count'] > 0 else 0
            data['avg_education'] = round(data['avg_education'] / data['candidate_count'], 1) if data['candidate_count'] > 0 else 0
        
        # Преобразуем в список для удобства работы в шаблоне
        qualification_data = list(vacancies_data.values())
        
        # Получаем данные для тепловой карты навыков
        # Получаем все категории навыков
        skill_categories = db.session.query(SkillCategory).filter(SkillCategory.is_active == True).all()
        
        # Получаем топ навыки по категориям
        skills_by_category = {}
        for category in skill_categories:
            # Получаем навыки из этой категории
            category_skills = db.session.query(
                Skill.id,
                Skill.name,
                func.count(CandidateSkill.id).label('candidate_count'),
                func.count(VacancySkill.id).label('vacancy_count')
            ).outerjoin(
                CandidateSkill, Skill.id == CandidateSkill.skill_id
            ).outerjoin(
                VacancySkill, Skill.id == VacancySkill.skill_id
            ).filter(
                Skill.category_id == category.id
            ).group_by(
                Skill.id
            ).order_by(
                func.count(VacancySkill.id).desc()
            ).limit(10).all()
            
            if category_skills:
                skills_by_category[category.id] = {
                    'name': category.name,
                    'skills': [
                        {
                            'name': s.name,
                            'candidate_percent': round(s.candidate_count / len(candidates) * 100, 1) if len(candidates) > 0 else 0,
                            'vacancy_percent': round(s.vacancy_count / len(vacancies_data) * 100, 1) if len(vacancies_data) > 0 else 0
                        }
                        for s in category_skills
                    ]
                }
        
        return render_template(
            'dashboard/statistics/qualification_analysis.html',
            qualification_data=qualification_data,
            skills_by_category=skills_by_category,
            candidates_data=candidates_data,
            industry_analysis=industry_analysis,
            industries=industries
        )
    except Exception as e:
        current_app.logger.error(f"Ошибка при анализе квалификации кандидатов: {str(e)}")
        flash(f"Ошибка при анализе квалификации кандидатов: {str(e)}", "danger")
        return redirect(url_for('dashboard.statistics'))

@dashboard_bp.route('/statistics/rejection_analysis')
@profile_time
@login_required
@hr_required
def rejection_analysis():
    """Страница с анализом отказов"""
    try:
        # Получаем данные об отказах кандидатам
        rejections = db.session.query(
            Candidate.id,
            Candidate.full_name,
            Candidate.vacancy_id,
            Candidate.rejection_reason,
            Candidate.rejection_stage,
            Vacancy.title.label('vacancy_title')
        ).join(Vacancy).filter(
            Candidate.status_id == 5,  # Статус "Отказ"
            Candidate.rejection_reason.isnot(None)
        ).all()
        
        # Преобразуем в DataFrame для удобства анализа
        df = pd.DataFrame([(r.id, r.full_name, r.vacancy_id, r.rejection_reason, 
                           r.rejection_stage, r.vacancy_title) for r in rejections], 
                          columns=['id', 'full_name', 'vacancy_id', 'reason', 'stage', 'vacancy_title'])
        
        # Группируем по причинам отказа
        reason_counts = df['reason'].value_counts().reset_index()
        reason_counts.columns = ['reason', 'count']
        
        # Группируем по этапам отказа
        stage_counts = df['stage'].value_counts().reset_index()
        stage_counts.columns = ['stage', 'count']
        
        # Анализ корреляций между этапом отказа и характеристиками кандидата
        # В реальном приложении здесь был бы более сложный анализ
        
        # Получаем данные об отказах кандидатов от предложений
        candidate_rejections = db.session.query(
            Candidate.id,
            Candidate.full_name,
            Candidate.vacancy_id,
            Candidate.candidate_rejection_reason,
            Vacancy.title.label('vacancy_title')
        ).join(Vacancy).filter(
            Candidate.status_id == 7,  # Статус "Отказался от предложения"
            Candidate.candidate_rejection_reason.isnot(None)
        ).all()
        
        # Преобразуем в DataFrame
        cand_df = pd.DataFrame([(r.id, r.full_name, r.vacancy_id, r.candidate_rejection_reason, 
                               r.vacancy_title) for r in candidate_rejections], 
                              columns=['id', 'full_name', 'vacancy_id', 'reason', 'vacancy_title'])
        
        # Группируем по причинам отказа кандидатов
        cand_reason_counts = cand_df['reason'].value_counts().reset_index()
        cand_reason_counts.columns = ['reason', 'count']
        
        return render_template(
            'dashboard/statistics/rejection_analysis.html',
            hr_rejections=df.to_dict('records'),
            reason_counts=reason_counts.to_dict('records'),
            stage_counts=stage_counts.to_dict('records'),
            candidate_rejections=cand_df.to_dict('records'),
            cand_reason_counts=cand_reason_counts.to_dict('records')
        )
    except Exception as e:
        current_app.logger.error(f"Ошибка при анализе отказов: {str(e)}")
        flash(f"Ошибка при анализе отказов: {str(e)}", "danger")
        return redirect(url_for('dashboard.statistics'))

@dashboard_bp.route('/statistics/predictive_analytics')
@profile_time
@login_required
@hr_required
def predictive_analytics():
    """Страница с прогнозной аналитикой"""
    try:
        # Получаем данные о вакансиях и времени их закрытия
        vacancies = db.session.query(
            Vacancy.id,
            Vacancy.title,
            Vacancy.created_at,
            Vacancy.closed_at,
            Vacancy.difficulty_level,
            Vacancy.location,
            func.count(Candidate.id).label('candidate_count')
        ).outerjoin(Candidate).group_by(Vacancy.id).filter(
            Vacancy.status == 'closed'
        ).all()
        
        # Преобразуем в DataFrame для удобства анализа
        df = pd.DataFrame([(v.id, v.title, v.created_at, v.closed_at, v.difficulty_level, 
                           v.location, v.candidate_count) for v in vacancies], 
                          columns=['id', 'title', 'created_at', 'closed_at', 'difficulty_level', 
                                 'location', 'candidate_count'])
        
        # Рассчитываем время закрытия в днях
        df['time_to_fill'] = (df['closed_at'] - df['created_at']).dt.days
        
        # Создаем модель прогнозирования времени закрытия вакансии
        # В реальном приложении здесь был бы код для обучения модели машинного обучения
        # Для демонстрации используем простую формулу
        
        # Прогнозируем вероятность принятия предложения
        # В реальном приложении здесь был бы код для обучения модели машинного обучения
        # Для демонстрации используем случайные данные
        
        # Получаем открытые вакансии для прогноза
        open_vacancies = Vacancy.query.filter(Vacancy.status == 'active').all()
        
        predictions = []
        for vacancy in open_vacancies:
            # Простая формула для прогноза времени закрытия
            # В реальном приложении здесь был бы прогноз от модели машинного обучения
            difficulty_factor = {'easy': 0.8, 'medium': 1.0, 'hard': 1.5}.get(vacancy.difficulty_level, 1.0)
            candidate_count = Candidate.query.filter(Candidate.vacancy_id == vacancy.id).count()
            
            if candidate_count > 0:
                predicted_days = int(30 * difficulty_factor * (10 / (candidate_count + 5)))
            else:
                predicted_days = int(45 * difficulty_factor)
            
            # Прогноз вероятности закрытия вакансии
            if candidate_count > 10:
                probability = min(90, 30 + candidate_count * 3)
            else:
                probability = max(10, candidate_count * 5)
            
            predictions.append({
                'id': vacancy.id,
                'title': vacancy.title,
                'predicted_days': predicted_days,
                'probability': probability,
                'candidate_count': candidate_count,
                'created_at': vacancy.created_at,
                'days_open': (datetime.datetime.now() - vacancy.created_at).days
            })
        
        # Рекомендации по оптимальным условиям
        recommendations = [
            "Для IT-специалистов: предложение удаленной работы увеличивает вероятность принятия на 35%",
            "Для вакансий уровня Senior: конкурентная зарплата важнее, чем дополнительные бонусы",
            "Для маркетинговых позиций: возможность профессионального роста является ключевым фактором",
            "Для вакансий с высокой конкуренцией: ускорение процесса найма критично для успеха",
            "Для технических специалистов: интересные проекты и современный стек технологий увеличивают конверсию"
        ]
        
        return render_template(
            'dashboard/statistics/predictive_analytics.html',
            historical_data=df.to_dict('records'),
            predictions=predictions,
            recommendations=recommendations
        )
    except Exception as e:
        current_app.logger.error(f"Ошибка при формировании прогнозной аналитики: {str(e)}")
        flash(f"Ошибка при формировании прогнозной аналитики: {str(e)}", "danger")
        return redirect(url_for('dashboard.statistics'))

@dashboard_bp.route('/statistics/seasonal_trends')
@profile_time
@login_required
@hr_required
def seasonal_trends():
    """Страница с анализом сезонных трендов"""
    try:
        # Получаем данные о кандидатах по месяцам
        current_year = datetime.datetime.now().year
        start_date = datetime.datetime(current_year - 1, 1, 1)
        
        candidates = db.session.query(
            func.date_trunc('month', Candidate.created_at).label('month'),
            func.count(Candidate.id).label('count'),
            func.avg(Candidate.ai_match_percent).label('avg_quality')
        ).filter(
            Candidate.created_at >= start_date
        ).group_by(
            func.date_trunc('month', Candidate.created_at)
        ).order_by(
            func.date_trunc('month', Candidate.created_at)
        ).all()
        
        # Преобразуем в DataFrame для удобства анализа
        df = pd.DataFrame([(c.month, c.count, c.avg_quality) for c in candidates], 
                          columns=['month', 'count', 'avg_quality'])
        
        # Форматируем даты для отображения
        df['month_name'] = df['month'].dt.strftime('%b %Y')
        
        # Округляем качество кандидатов
        df['avg_quality'] = df['avg_quality'].fillna(0).round(1)
        
        # Прогноз на будущие месяцы
        # В реальном приложении здесь был бы код для временного ряда и прогнозирования
        # Для демонстрации используем простую модель
        
        last_months = df.tail(3)
        if len(last_months) > 0:
            avg_growth = last_months['count'].pct_change().mean()
            last_count = df['count'].iloc[-1]
            
            # Прогноз на следующие 3 месяца
            forecast = []
            for i in range(1, 4):
                month = df['month'].iloc[-1] + pd.DateOffset(months=i)
                predicted_count = int(last_count * (1 + avg_growth * i))
                forecast.append({
                    'month': month,
                    'month_name': month.strftime('%b %Y'),
                    'predicted_count': predicted_count
                })
        else:
            forecast = []
        
        # Данные для графиков
        chart_data = {
            'labels': df['month_name'].tolist(),
            'counts': df['count'].tolist(),
            'quality': df['avg_quality'].tolist(),
            'forecast_labels': [f['month_name'] for f in forecast],
            'forecast_counts': [f['predicted_count'] for f in forecast]
        }
        
        return render_template(
            'dashboard/statistics/seasonal_trends.html',
            monthly_data=df.to_dict('records'),
            forecast=forecast,
            chart_data=chart_data
        )
    except Exception as e:
        current_app.logger.error(f"Ошибка при анализе сезонных трендов: {str(e)}")
        flash(f"Ошибка при анализе сезонных трендов: {str(e)}", "danger")
        return redirect(url_for('dashboard.statistics')) 