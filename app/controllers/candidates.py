#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_from_directory, abort
from flask_login import login_required, current_user
from app import db
from app.models import Candidate, Vacancy, C_Candidate_Status, SystemLog, Notification
from app.forms.candidate import CandidateCommentForm, CandidateStatusForm
from app.utils.ai_service import request_ai_analysis
from app.utils.email_service import send_status_change_notification
import os
from werkzeug.utils import secure_filename
import datetime
import json
import logging
from sqlalchemy import desc

# Получаем логгер
logger = logging.getLogger(__name__)

candidates_bp = Blueprint('candidates', __name__, url_prefix='/candidates')

@candidates_bp.route('/')
@login_required
def index():
    """Список всех кандидатов HR-менеджера"""
    # Получаем параметры фильтра
    vacancy_id = request.args.get('vacancy_id', type=int)
    status_id = request.args.get('status_id', type=int)
    sort_by = request.args.get('sort_by', 'date')
    
    # Базовый запрос
    query = db.session.query(Candidate).join(
        Vacancy, Candidate.vacancy_id == Vacancy.id
    ).filter(
        Vacancy.created_by == current_user.id
    )
    
    # Применяем фильтры
    if vacancy_id:
        query = query.filter(Candidate.vacancy_id == vacancy_id)
    
    if status_id:
        query = query.filter(Candidate.id_c_candidate_status == status_id)
    
    # Сортировка
    if sort_by == 'date':
        query = query.order_by(Candidate.created_at.desc())
    elif sort_by == 'match':
        query = query.order_by(Candidate.ai_match_percent.desc())
    else:
        query = query.order_by(Candidate.created_at.desc())
    
    candidates = query.all()
    
    # Получаем все вакансии HR-менеджера для фильтра
    vacancies = Vacancy.query.filter_by(created_by=current_user.id).all()
    
    # Получаем все статусы кандидатов для фильтра
    statuses = C_Candidate_Status.query.all()
    
    return render_template(
        'candidates/index.html',
        candidates=candidates,
        vacancies=vacancies,
        statuses=statuses,
        vacancy_id=vacancy_id,
        status_id=status_id,
        sort_by=sort_by,
        title='Кандидаты'
    )

@candidates_bp.route('/<int:id>')
@login_required
def view(id):
    """Детальная информация о кандидате"""
    candidate = Candidate.query.get_or_404(id)
    
    # Проверяем, принадлежит ли вакансия текущему HR-менеджеру
    if candidate.vacancy.created_by != current_user.id:
        flash('У вас нет доступа к просмотру этого кандидата', 'danger')
        return redirect(url_for('candidates.index'))
    
    # Получаем статусы для формы изменения статуса
    statuses = C_Candidate_Status.query.all()
    
    # Определяем путь к файлу резюме (если есть)
    resume_file_url = None
    if candidate.resume_path:
        resume_file_url = url_for('files.download_resume', filename=os.path.basename(candidate.resume_path))
    
    return render_template(
        'candidates/view.html',
        candidate=candidate,
        statuses=statuses,
        resume_file_url=resume_file_url,
        title=f'Кандидат: {candidate.full_name}'
    )

@candidates_bp.route('/<int:id>/change_status', methods=['POST'])
@login_required
def change_status(id):
    """Изменение статуса кандидата"""
    candidate = Candidate.query.get_or_404(id)
    
    # Проверяем, принадлежит ли вакансия текущему HR-менеджеру
    if candidate.vacancy.created_by != current_user.id:
        flash('У вас нет доступа к редактированию этого кандидата', 'danger')
        return redirect(url_for('candidates.index'))
    
    # Получаем новый статус из формы
    new_status_id = request.form.get('status_id', type=int)
    interview_date_str = request.form.get('interview_date')
    
    if not new_status_id:
        flash('Не указан новый статус', 'danger')
        return redirect(url_for('candidates.view', id=id))
    
    # Получаем статус из БД для проверки
    status = C_Candidate_Status.query.get(new_status_id)
    if not status:
        flash('Указан некорректный статус', 'danger')
        return redirect(url_for('candidates.view', id=id))
    
    # Обновляем статус
    old_status_id = candidate.id_c_candidate_status
    candidate.id_c_candidate_status = new_status_id
    
    # Если новый статус "Собеседование", то обновляем дату собеседования
    if new_status_id == 2 and interview_date_str:  # ID статуса "Назначено интервью" = 2
        try:
            interview_date = datetime.strptime(interview_date_str, '%Y-%m-%dT%H:%M')
            candidate.interview_date = interview_date
        except ValueError:
            flash('Некорректный формат даты собеседования', 'warning')
    
    db.session.commit()
    
    # Логируем изменение статуса
    SystemLog.log(
        event_type="candidate_status_change",
        description=f"Изменен статус кандидата ID={id} с '{old_status_id}' на '{new_status_id}'",
        user_id=current_user.id,
        ip_address=request.remote_addr
    )
    
    flash(f'Статус кандидата успешно изменен на "{status.name}"', 'success')
    return redirect(url_for('candidates.view', id=id))

@candidates_bp.route('/<int:id>/add_comment', methods=['POST'])
@login_required
def add_comment(id):
    """Добавление комментария к кандидату"""
    candidate = Candidate.query.get_or_404(id)
    
    # Проверяем, принадлежит ли вакансия текущему HR-менеджеру
    if candidate.vacancy.created_by != current_user.id:
        flash('У вас нет доступа к редактированию этого кандидата', 'danger')
        return redirect(url_for('candidates.index'))
    
    # Получаем комментарий из формы
    comment = request.form.get('comment', '').strip()
    
    if comment:
        # Обновляем комментарий
        candidate.hr_comment = comment
        db.session.commit()
        
        # Логируем добавление комментария
        SystemLog.log(
            event_type="candidate_comment_add",
            description=f"Добавлен комментарий к кандидату ID={id}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        flash('Комментарий успешно добавлен', 'success')
    else:
        flash('Комментарий не может быть пустым', 'warning')
    
    return redirect(url_for('candidates.view', id=id))

@candidates_bp.route('/<int:id>/download_resume')
@login_required
def download_resume(id):
    """Скачивание резюме кандидата"""
    candidate = Candidate.query.get_or_404(id)
    vacancy = Vacancy.query.get(candidate.vacancy_id)
    
    # Проверка доступа для HR-менеджера
    if current_user.role == 'hr' and vacancy.created_by != current_user.id:
        flash('У вас нет прав для скачивания резюме этого кандидата', 'danger')
        return redirect(url_for('candidates.index'))
    
    if not candidate.resume_path:
        flash('Резюме не найдено', 'danger')
        return redirect(url_for('candidates.view', id=candidate.id))
    
    # Определяем директорию для загрузки файлов из конфигурации
    upload_folder = current_app.config['UPLOAD_FOLDER']
    filename = os.path.basename(candidate.resume_path)
    
    # Логирование
    SystemLog.log(
        event_type="resume_download",
        description=f"Скачивание резюме кандидата ID={candidate.id}",
        user_id=current_user.id,
        ip_address=request.remote_addr
    )
    
    return send_from_directory(
        upload_folder, 
        filename, 
        as_attachment=True, 
        download_name=f"resume_{candidate.full_name}_{datetime.datetime.now().strftime('%Y%m%d')}{os.path.splitext(filename)[1]}"
    )

@candidates_bp.route('/<int:id>/start_analysis', methods=['POST'])
@login_required
def start_analysis(id):
    """Запуск AI-анализа кандидата"""
    candidate = Candidate.query.get_or_404(id)
    vacancy = Vacancy.query.get(candidate.vacancy_id)
    
    # Проверка доступа для HR-менеджера
    if current_user.role == 'hr' and vacancy.created_by != current_user.id:
        flash('У вас нет прав для запуска анализа этого кандидата', 'danger')
        return redirect(url_for('candidates.index'))
    
    # Проверяем, есть ли текст резюме
    if not candidate.resume_text:
        flash('Нет текста резюме для анализа', 'danger')
        return redirect(url_for('candidates.view', id=candidate.id))
    
    # Запускаем анализ (может быть асинхронным с использованием Celery)
    try:
        # Логирование начала анализа
        SystemLog.log(
            event_type="ai_analysis_start",
            description=f"Запущен AI-анализ кандидата ID={candidate.id}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        # Запрос к AI API
        result = request_ai_analysis(candidate)
        
        if result:
            flash('Анализ кандидата успешно завершен', 'success')
        else:
            flash('Произошла ошибка при анализе кандидата', 'danger')
            
    except Exception as e:
        flash(f'Ошибка при запуске анализа: {str(e)}', 'danger')
    
    return redirect(url_for('candidates.view', id=candidate.id))

@candidates_bp.route('/track/<tracking_code>')
def track(tracking_code):
    """Публичная страница для отслеживания статуса кандидата"""
    candidate = Candidate.query.filter_by(tracking_code=tracking_code).first_or_404()
    
    return render_template(
        'candidates/track.html',
        candidate=candidate,
        vacancy=candidate.vacancy,
        title='Отслеживание статуса заявки'
    )

@candidates_bp.route('/api/candidates')
@login_required
def api_candidates():
    """API для получения списка кандидатов (для AJAX-запросов)"""
    vacancy_id = request.args.get('vacancy_id', type=int)
    status_id = request.args.get('status_id', type=int)
    
    query = db.session.query(Candidate).join(
        Vacancy, Candidate.vacancy_id == Vacancy.id
    ).filter(
        Vacancy.created_by == current_user.id
    )
    
    if vacancy_id:
        query = query.filter(Candidate.vacancy_id == vacancy_id)
    
    if status_id:
        query = query.filter(Candidate.id_c_candidate_status == status_id)
    
    candidates = query.all()
    
    # Преобразуем данные в JSON
    result = []
    for candidate in candidates:
        result.append({
            'id': candidate.id,
            'full_name': candidate.full_name,
            'vacancy': candidate.vacancy.title,
            'status': candidate.c_candidate_status.name if candidate.c_candidate_status else 'Заявка подана',
            'created_at': candidate.created_at.strftime('%d.%m.%Y'),
            'ai_match_percent': candidate.ai_match_percent or 0
        })
    
    return jsonify(result) 