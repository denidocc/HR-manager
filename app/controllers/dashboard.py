#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Vacancy, Candidate, C_Candidate_Status, Notification, SystemLog
from sqlalchemy import func, desc, and_
import datetime

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
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