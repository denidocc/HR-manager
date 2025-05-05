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

candidates_bp = Blueprint('candidates', __name__, url_prefix='/candidates')

@candidates_bp.route('/')
@login_required
def index():
    """Список всех кандидатов"""
    # Получаем параметры фильтрации
    vacancy_id = request.args.get('vacancy_id', type=int)
    status_id = request.args.get('status_id', type=int)
    sort_by = request.args.get('sort', 'date')
    
    # Базовый запрос
    query = Candidate.query
    
    # Применяем фильтры
    if vacancy_id:
        query = query.filter_by(vacancy_id=vacancy_id)
    
    if status_id:
        query = query.filter_by(id_c_candidate_status=status_id)
    
    # Сортировка
    if sort_by == 'date':
        query = query.order_by(Candidate.created_at.desc())
    elif sort_by == 'match':
        query = query.order_by(Candidate.ai_match_percent.desc())
    elif sort_by == 'name':
        query = query.order_by(Candidate.full_name)
    
    candidates = query.all()
    
    # Получаем все вакансии и статусы для фильтров
    vacancies = Vacancy.query.all()
    statuses = C_Candidate_Status.query.all()
    
    return render_template(
        'candidates/index.html',
        candidates=candidates,
        vacancies=vacancies,
        statuses=statuses,
        current_vacancy_id=vacancy_id,
        current_status_id=status_id,
        current_sort=sort_by,
        title='Управление кандидатами'
    )

@candidates_bp.route('/<int:id>/view')
@login_required
def view(id):
    """Просмотр детальной информации о кандидате"""
    candidate = Candidate.query.get_or_404(id)
    vacancy = Vacancy.query.get(candidate.vacancy_id)
    
    # Форма для добавления комментария
    comment_form = CandidateCommentForm()
    
    # Форма для изменения статуса
    status_form = CandidateStatusForm()
    status_form.id_c_candidate_status.choices = [
        (s.id, s.name) for s in C_Candidate_Status.query.all()
    ]
    status_form.id_c_candidate_status.data = candidate.id_c_candidate_status
    
    # Логирование просмотра кандидата
    SystemLog.log(
        event_type="view_candidate",
        description=f"Просмотр карточки кандидата ID={candidate.id}",
        user_id=current_user.id,
        ip_address=request.remote_addr
    )
    
    return render_template(
        'candidates/view.html',
        candidate=candidate,
        vacancy=vacancy,
        comment_form=comment_form,
        status_form=status_form,
        title=f'Кандидат: {candidate.full_name}'
    )

@candidates_bp.route('/<int:id>/change_status', methods=['POST'])
@login_required
def change_status(id):
    """Изменение статуса кандидата"""
    candidate = Candidate.query.get_or_404(id)
    
    form = CandidateStatusForm()
    form.id_c_candidate_status.choices = [
        (s.id, s.name) for s in C_Candidate_Status.query.all()
    ]
    
    if form.validate_on_submit():
        old_status = candidate.c_candidate_status.name
        
        # Обновляем статус
        candidate.id_c_candidate_status = form.id_c_candidate_status.data
        
        # Если статус изменен на "Назначено интервью", сохраняем дату интервью
        if candidate.c_candidate_status.name == "Назначено интервью" and form.interview_date.data:
            candidate.interview_date = form.interview_date.data
        
        db.session.commit()
        
        new_status = candidate.c_candidate_status.name
        
        # Логирование
        SystemLog.log(
            event_type="candidate_status_change",
            description=f"Изменен статус кандидата ID={candidate.id} с '{old_status}' на '{new_status}'",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        # Создание уведомления для кандидата
        notification_type = "status_update"
        message = f"Статус вашей заявки на вакансию '{candidate.vacancy.title}' изменен на '{new_status}'."
        
        if new_status == "Назначено интервью":
            notification_type = "interview_invitation"
            interview_date_str = candidate.interview_date.strftime("%d.%m.%Y %H:%M") if candidate.interview_date else "будет согласована дополнительно"
            message = f"Приглашаем вас на собеседование по вакансии '{candidate.vacancy.title}'. Дата: {interview_date_str}."
        elif new_status == "Отклонен":
            notification_type = "rejection"
            message = f"К сожалению, ваша кандидатура на вакансию '{candidate.vacancy.title}' была отклонена. Благодарим за интерес к нашей компании."
        elif new_status == "Принят":
            notification_type = "offer"
            message = f"Поздравляем! Вам сделано предложение о работе на позицию '{candidate.vacancy.title}'. Ожидаем вашего ответа."
        
        # Создаем уведомление
        notification = Notification(
            candidate_id=candidate.id,
            type=notification_type,
            message=message
        )
        db.session.add(notification)
        db.session.commit()
        
        # Отправляем уведомление по email
        send_status_change_notification(candidate, notification)
        
        flash(f'Статус кандидата обновлен на "{new_status}"', 'success')
        return redirect(url_for('candidates.view', id=candidate.id))
    
    flash('Произошла ошибка при обновлении статуса', 'danger')
    return redirect(url_for('candidates.view', id=candidate.id))

@candidates_bp.route('/<int:id>/add_comment', methods=['POST'])
@login_required
def add_comment(id):
    """Добавление комментария к кандидату"""
    candidate = Candidate.query.get_or_404(id)
    form = CandidateCommentForm()
    
    if form.validate_on_submit():
        # Обновляем комментарий
        candidate.hr_comment = form.comment.data
        db.session.commit()
        
        # Логирование
        SystemLog.log(
            event_type="candidate_comment_added",
            description=f"Добавлен комментарий к кандидату ID={candidate.id}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        flash('Комментарий добавлен', 'success')
    else:
        flash('Произошла ошибка при добавлении комментария', 'danger')
    
    return redirect(url_for('candidates.view', id=candidate.id))

@candidates_bp.route('/<int:id>/download_resume')
@login_required
def download_resume(id):
    """Скачивание резюме кандидата"""
    candidate = Candidate.query.get_or_404(id)
    
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