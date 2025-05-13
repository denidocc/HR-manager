#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, jsonify, request, current_app, render_template
from flask_login import login_required, current_user
from app import db
from app.models import Candidate, Vacancy, SystemLog
from app.utils.ai_service import request_ai_analysis, get_analysis_status
import json
from app.utils.decorators import profile_time
ai_analysis_bp = Blueprint('ai_analysis', __name__, url_prefix='/ai_analysis')

@ai_analysis_bp.route('/start/<int:candidate_id>', methods=['POST'])
@profile_time
@login_required
def start_analysis(candidate_id):
    """Запуск AI-анализа для кандидата"""
    candidate = Candidate.query.get_or_404(candidate_id)
    
    # Проверяем, есть ли текст резюме
    if not candidate.resume_text:
        return jsonify({
            'status': 'error',
            'message': 'Нет текста резюме для анализа. Загрузите резюме и попробуйте снова.'
        }), 400
    
    try:
        # Логирование начала анализа
        SystemLog.log(
            event_type="ai_analysis_start",
            description=f"Запущен AI-анализ кандидата ID={candidate.id}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        # Запрос к API OpenAI
        job_id = request_ai_analysis(candidate)
        
        return jsonify({
            'status': 'success',
            'message': 'Анализ кандидата запущен',
            'job_id': job_id
        })
    
    except Exception as e:
        current_app.logger.error(f"Ошибка при запуске AI-анализа: {str(e)}")
        
        # Логирование ошибки
        SystemLog.log(
            event_type="ai_analysis_error",
            description=f"Ошибка при запуске AI-анализа кандидата ID={candidate.id}: {str(e)}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        return jsonify({
            'status': 'error',
            'message': f'Ошибка при запуске анализа: {str(e)}'
        }), 500

@ai_analysis_bp.route('/status/<job_id>')
@profile_time
@login_required
def check_status(job_id):
    """Проверка статуса AI-анализа по ID задачи"""
    try:
        status = get_analysis_status(job_id)
        
        return jsonify({
            'status': 'success',
            'job_status': status
        })
    
    except Exception as e:
        current_app.logger.error(f"Ошибка при проверке статуса AI-анализа: {str(e)}")
        
        return jsonify({
            'status': 'error',
            'message': f'Ошибка при проверке статуса анализа: {str(e)}'
        }), 500

@ai_analysis_bp.route('/result/<int:candidate_id>')
@profile_time
@login_required
def view_result(candidate_id):
    """Просмотр результатов AI-анализа"""
    candidate = Candidate.query.get_or_404(candidate_id)
    vacancy = Vacancy.query.get(candidate.vacancy_id)
    
    # Логирование просмотра результатов анализа
    SystemLog.log(
        event_type="ai_analysis_view",
        description=f"Просмотр результатов AI-анализа кандидата ID={candidate.id}",
        user_id=current_user.id,
        ip_address=request.remote_addr
    )
    
    # Проверяем, есть ли результаты анализа
    if not candidate.ai_match_percent:
        return jsonify({
            'status': 'error',
            'message': 'Результаты анализа для данного кандидата отсутствуют'
        }), 404
    
    # Формируем данные для визуализации
    categories = ['Локация', 'Опыт работы', 'Технические навыки', 'Образование']
    scores = [
        candidate.ai_score_location,
        candidate.ai_score_experience,
        candidate.ai_score_tech,
        candidate.ai_score_education
    ]
    
    # Комментарии к оценкам
    comments = {
        'location': candidate.ai_score_comments_location,
        'experience': candidate.ai_score_comments_experience,
        'tech': candidate.ai_score_comments_tech,
        'education': candidate.ai_score_comments_education
    }
    
    # Разбиваем плюсы и минусы на списки
    pros = candidate.ai_pros.split('\n') if candidate.ai_pros else []
    cons = candidate.ai_cons.split('\n') if candidate.ai_cons else []
    
    return render_template(
        'ai_analysis/result.html',
        candidate=candidate,
        vacancy=vacancy,
        categories=categories,
        scores=scores,
        comments=comments,
        pros=pros,
        cons=cons,
        title=f'AI-анализ: {candidate.full_name}'
    )

@ai_analysis_bp.route('/api/result/<int:candidate_id>')
@profile_time
@login_required
def api_result(candidate_id):
    """API для получения результатов AI-анализа в формате JSON"""
    candidate = Candidate.query.get_or_404(candidate_id)
    
    # Проверяем, есть ли результаты анализа
    if not candidate.ai_match_percent:
        return jsonify({
            'status': 'error',
            'message': 'Результаты анализа для данного кандидата отсутствуют'
        }), 404
    
    result = {
        'candidate_id': candidate.id,
        'full_name': candidate.full_name,
        'vacancy_title': candidate.vacancy.title,
        'match_percent': candidate.ai_match_percent,
        'pros': candidate.ai_pros.split('\n') if candidate.ai_pros else [],
        'cons': candidate.ai_cons.split('\n') if candidate.ai_cons else [],
        'recommendation': candidate.ai_recommendation,
        'scores': {
            'location': candidate.ai_score_location,
            'experience': candidate.ai_score_experience,
            'tech_skills': candidate.ai_score_tech,
            'education': candidate.ai_score_education
        },
        'comments': {
            'location': candidate.ai_score_comments_location,
            'experience': candidate.ai_score_comments_experience,
            'tech_skills': candidate.ai_score_comments_tech,
            'education': candidate.ai_score_comments_education
        },
        'mismatch_notes': candidate.ai_mismatch_notes
    }
    
    return jsonify({
        'status': 'success',
        'data': result
    })

@ai_analysis_bp.route('/explanation')
@profile_time
@login_required
def explanation():
    """Страница с объяснением методологии AI-анализа"""
    return render_template(
        'ai_analysis/explanation.html',
        title='Методология AI-анализа'
    ) 