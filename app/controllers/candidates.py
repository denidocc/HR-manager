#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_from_directory, abort, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Candidate, Vacancy, SystemLog, Notification, C_Selection_Stage
from app.forms.candidate import CandidateCommentForm
from app.utils.ai_service import request_ai_analysis
from app.utils.email_service import send_status_change_notification
from app.utils.decorators import profile_time
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import json
import logging
from sqlalchemy import desc, func, cast
import sqlalchemy as sa
import fitz  # PyMuPDF для работы с PDF
import numpy as np
import cv2
from openai import OpenAI
import base64
import docx
from app.models.c_rejection_reason import C_Rejection_Reason
from app.controllers.auth import hr_required

# Получаем логгер
logger = logging.getLogger(__name__)

candidates_bp = Blueprint('candidates', __name__, url_prefix='/candidates')

@candidates_bp.route('/')
@profile_time
@login_required
def index():
    """Список всех кандидатов HR-менеджера в формате канбан-доски"""
    # Получаем параметры фильтра
    vacancy_id = request.args.get('vacancy_id', type=int)
    sort_by = request.args.get('sort_by', 'date')
    
    # Получаем этапы отбора текущего HR-менеджера
    selection_stages = current_user.get_selection_stages()
    
    # Базовый запрос с дешифровкой полей email и phone
    query = db.session.query(
        Candidate.id,
        Candidate.vacancy_id,
        Candidate.full_name,
        func.pgp_sym_decrypt(
            cast(Candidate._email, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('email'),
        func.pgp_sym_decrypt(
            cast(Candidate._phone, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('phone'),
        Candidate.created_at,
        Candidate.ai_match_percent,
        Candidate.id_c_selection_stage,
        Vacancy.title.label('vacancy_title'),
        Vacancy.id.label('vacancy_id'),
        C_Selection_Stage.name.label('stage_name'),
        C_Selection_Stage.color.label('stage_color')
    ).join(
        Vacancy, Candidate.vacancy_id == Vacancy.id
    ).join(
        C_Selection_Stage, Candidate.id_c_selection_stage == C_Selection_Stage.id
    ).filter(
        Vacancy.created_by == current_user.id
    )
    
    # Применяем фильтр по вакансии
    if vacancy_id:
        query = query.filter(Candidate.vacancy_id == vacancy_id)
    
    # Сортировка
    if sort_by == 'date':
        query = query.order_by(Candidate.created_at.desc())
    elif sort_by == 'match':
        query = query.order_by(Candidate.ai_match_percent.desc())
    else:
        query = query.order_by(Candidate.created_at.desc())
    
    # Выполняем запрос
    candidates_data = query.all()
    
    # Создаем структуру канбан-доски: словарь, где ключи - id этапов, а значения - списки кандидатов
    kanban_board = {stage.id: [] for stage in selection_stages}
    
    # Распределяем кандидатов по колонкам
    for c in candidates_data:
        candidate = {
            'id': c.id,
            'vacancy_id': c.vacancy_id,
            'vacancy': {
                'id': c.vacancy_id,
                'title': c.vacancy_title
            },
            'full_name': c.full_name,
            'email': c.email,
            'phone': c.phone,
            'created_at': c.created_at,
            'ai_match_percent': c.ai_match_percent,
            'id_c_selection_stage': c.id_c_selection_stage,
            'selection_stage': {
                'name': c.stage_name,
                'color': c.stage_color
            }
        }
        kanban_board[c.id_c_selection_stage].append(candidate)
    
    # Получаем все вакансии HR-менеджера для фильтра
    vacancies = Vacancy.query.filter_by(created_by=current_user.id).all()
    
    return render_template(
        'candidates/index.html',
        kanban_board=kanban_board,
        selection_stages=selection_stages,
        vacancies=vacancies,
        vacancy_id=vacancy_id,
        sort_by=sort_by,
        title='Канбан кандидатов'
    )

@candidates_bp.route('/<int:id>')
@profile_time
@login_required
def view(id):
    """Детальная информация о кандидате"""
    # Сначала получаем кандидата с расшифрованными полями
    candidate_data = db.session.query(
        Candidate.id,
        Candidate.vacancy_id,
        Candidate.full_name,
        Candidate.base_answers,
        Candidate.vacancy_answers,
        Candidate.soft_answers,
        Candidate.resume_path,
        Candidate.resume_text,
        Candidate.cover_letter,
        Candidate.ai_match_percent,
        Candidate.ai_pros,
        Candidate.ai_cons,
        Candidate.ai_recommendation,
        Candidate.ai_score_location,
        Candidate.ai_score_experience,
        Candidate.ai_score_tech,
        Candidate.ai_score_education,
        Candidate.ai_score_comments_location,
        Candidate.ai_score_comments_experience,
        Candidate.ai_score_comments_tech,
        Candidate.ai_score_comments_education,
        Candidate.ai_mismatch_notes,
        Candidate.ai_data_consistency,
        Candidate.ai_answer_quality,
        Candidate.ai_data_completeness,
        Candidate.ai_analysis_data,
        Candidate.interview_date,
        Candidate.hr_comment,
        Candidate.created_at,
        Candidate.updated_at,
        Candidate.tracking_code,
        Candidate.id_c_rejection_reason,
        func.pgp_sym_decrypt(
            cast(Candidate._email, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('email'),
        func.pgp_sym_decrypt(
            cast(Candidate._phone, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('phone'),
        Candidate.id_c_selection_stage,
        Vacancy.title.label('vacancy_title')
    ).join(
        Vacancy, Candidate.vacancy_id == Vacancy.id
    ).filter(Candidate.id == id).first_or_404()
    
    # Получаем обычную модель кандидата для связей
    candidate = Candidate.query.get_or_404(id)
    
    # Получаем данные о вакансии и этапе
    vacancy = Vacancy.query.get(candidate_data.vacancy_id)
    stage = C_Selection_Stage.query.get(candidate_data.id_c_selection_stage)
    
    # Получаем причины отклонения
    rejection_reasons = C_Rejection_Reason.query.filter_by(is_active=True).order_by(C_Rejection_Reason.order).all()
    
    # Обрабатываем вопросы и ответы чтобы отобразить корректные данные
    formatted_vacancy_answers = {}
    if candidate_data.vacancy_answers and vacancy.questions_json:
        # Создаем словарь с id -> текст вопроса
        question_texts = {str(q['id']): q['text'] for q in vacancy.questions_json}
        
        # Для каждого ответа получаем текст вопроса и создаем пару "текст вопроса": ответ
        for question_id, answer in candidate_data.vacancy_answers.items():
            question_text = question_texts.get(question_id, f"Вопрос {question_id}")
            formatted_vacancy_answers[question_text] = answer
    
    # Аналогично форматируем soft-skills вопросы
    formatted_soft_answers = {}
    if candidate_data.soft_answers and vacancy.soft_questions_json:
        # Создаем словарь с id -> текст вопроса
        soft_question_texts = {str(q['id']): q['text'] for q in vacancy.soft_questions_json}
        
        # Для каждого ответа получаем текст вопроса
        for question_id, answer in candidate_data.soft_answers.items():
            question_text = soft_question_texts.get(question_id, f"Вопрос {question_id}")
            formatted_soft_answers[question_text] = answer
    
    # Создаем объект с данными для шаблона
    candidate_view = {
        'id': candidate_data.id,
        'vacancy_id': candidate_data.vacancy_id,
        'vacancy': {
            'id': candidate_data.vacancy_id,
            'title': candidate_data.vacancy_title,
            'created_by': vacancy.created_by,
            'questions_json': vacancy.questions_json,
            'soft_questions_json': vacancy.soft_questions_json
        },
        'full_name': candidate_data.full_name,
        'email': candidate_data.email,
        'phone': candidate_data.phone,
        'base_answers': candidate_data.base_answers,
        'vacancy_answers': formatted_vacancy_answers,  # Используем форматированные ответы
        'soft_answers': formatted_soft_answers,  # Используем форматированные ответы
        'resume_path': candidate_data.resume_path,
        'resume_text': candidate_data.resume_text,
        'cover_letter': candidate_data.cover_letter,
        'ai_match_percent': candidate_data.ai_match_percent,
        'ai_pros': candidate_data.ai_pros.replace('{', '').replace('}', '').replace('"', '').split(',') if candidate_data.ai_pros else [],
        'ai_cons': candidate_data.ai_cons.replace('{', '').replace('}', '').replace('"', '').split(',') if candidate_data.ai_cons else [],
        'ai_recommendation': candidate_data.ai_recommendation,
        'ai_score_location': candidate_data.ai_score_location,
        'ai_score_experience': candidate_data.ai_score_experience,
        'ai_score_tech': candidate_data.ai_score_tech,
        'ai_score_education': candidate_data.ai_score_education,
        'ai_score_comments_location': candidate_data.ai_score_comments_location,
        'ai_score_comments_experience': candidate_data.ai_score_comments_experience,
        'ai_score_comments_tech': candidate_data.ai_score_comments_tech,
        'ai_score_comments_education': candidate_data.ai_score_comments_education,
        'ai_mismatch_notes': candidate_data.ai_mismatch_notes,
        'ai_data_consistency': candidate_data.ai_data_consistency if candidate_data.ai_data_consistency else {},
        'ai_answer_quality': candidate_data.ai_answer_quality if candidate_data.ai_answer_quality else {},
        'ai_data_completeness': candidate_data.ai_data_completeness if candidate_data.ai_data_completeness else {},
        'ai_analysis_data': candidate_data.ai_analysis_data if candidate_data.ai_analysis_data else {},
        'interview_date': candidate_data.interview_date,
        'hr_comment': candidate_data.hr_comment,
        'created_at': candidate_data.created_at,
        'updated_at': candidate_data.updated_at,
        'tracking_code': candidate_data.tracking_code,
        'selection_stage': stage,
        'id_c_selection_stage': candidate_data.id_c_selection_stage,
        'id_c_rejection_reason': candidate_data.id_c_rejection_reason,
        'notifications': candidate.notifications  # Берем из оригинальной модели
    }
    
    # Проверяем, принадлежит ли вакансия текущему HR-менеджеру
    if vacancy.created_by != current_user.id:
        flash('У вас нет доступа к просмотру этого кандидата', 'danger')
        return redirect(url_for('candidates.index'))
    
    # Получаем этапы для формы изменения этапа
    stages = C_Selection_Stage.query.all()
    
    # Определяем путь к файлу резюме (если есть)
    resume_file_url = None
    if candidate_data.resume_path:
        resume_file_url = url_for('files.download_file', filename=os.path.basename(candidate_data.resume_path))
    
    return render_template(
        'candidates/view.html',
        candidate=candidate_view,
        stages=stages,
        rejection_reasons=rejection_reasons,
        resume_file_url=resume_file_url,
        title=f'Кандидат: {candidate_data.full_name}'
    )

@candidates_bp.route('/change_status/<int:id>', methods=['POST'])
@profile_time
@login_required
def change_status(id):
    """Изменение этапа отбора кандидата"""
    candidate = Candidate.query.get_or_404(id)
    
    # Проверяем, что кандидат принадлежит вакансии текущего HR
    if not candidate.vacancy or candidate.vacancy.id_hr != current_user.id:
        flash('У вас нет доступа к этому кандидату', 'danger')
        return redirect(url_for('candidates.index'))
    
    stage_id = request.form.get('stage_id', type=int)
    if not stage_id:
        flash('Не указан этап отбора', 'danger')
        return redirect(url_for('candidates.view', id=id))
    
    # Проверяем, что этап принадлежит текущему HR
    stage = C_Selection_Stage.query.get_or_404(stage_id)
    if stage.id_hr != current_user.id:
        flash('У вас нет доступа к этому этапу отбора', 'danger')
        return redirect(url_for('candidates.view', id=id))
    
    # Обновляем этап отбора
    candidate.id_c_selection_stage = stage_id
    
    # Логируем изменение
    log = SystemLog(
        action='change_stage',
        entity_type='candidate',
        entity_id=candidate.id,
        user_id=current_user.id,
        details=f'Изменен этап отбора на "{stage.name}"'
    )
    db.session.add(log)
    
    # Создаем уведомление
    notification = Notification(
        user_id=current_user.id,
        title='Изменение этапа отбора',
        message=f'Кандидат {candidate.full_name} переведен на этап "{stage.name}"',
        type='info'
    )
    db.session.add(notification)
    
    try:
        db.session.commit()
        flash('Этап отбора успешно обновлен', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении этапа отбора: {str(e)}', 'danger')
    
    return redirect(url_for('candidates.view', id=id))

@candidates_bp.route('/<int:id>/add_comment', methods=['POST'])
@profile_time
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
@profile_time
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
        download_name=f"resume_{candidate.full_name}_{datetime.now().strftime('%Y%m%d')}{os.path.splitext(filename)[1]}"
    )

@candidates_bp.route('/<int:id>/start_analysis', methods=['POST'])
@profile_time
@login_required
def start_analysis(id):
    """Запуск AI-анализа кандидата"""
    # Получаем данные кандидата с дешифровкой
    candidate_data = db.session.query(
        Candidate.id,
        Candidate.vacancy_id,
        Candidate.full_name,
        Candidate.resume_text,
        Candidate.base_answers,
        Candidate.vacancy_answers,
        Candidate.soft_answers,
        Candidate.cover_letter,
        func.pgp_sym_decrypt(
            cast(Candidate._email, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('email'),
        func.pgp_sym_decrypt(
            cast(Candidate._phone, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('phone')
    ).filter(Candidate.id == id).first_or_404()
    
    # Получаем обычную модель для обновления и связей
    candidate = Candidate.query.get_or_404(id)
    vacancy = Vacancy.query.get(candidate.vacancy_id)
    
    # Проверка доступа для HR-менеджера
    if current_user.role == 'hr' and vacancy.created_by != current_user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'У вас нет прав для запуска анализа этого кандидата'}), 403
        flash('У вас нет прав для запуска анализа этого кандидата', 'danger')
        return redirect(url_for('candidates.index'))
    
    # Проверяем, есть ли текст резюме
    if not candidate.resume_text:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'Нет текста резюме для анализа. Загрузите резюме и попробуйте снова.'}), 400
        flash('Нет текста резюме для анализа. Загрузите резюме и попробуйте снова.', 'warning')
        return redirect(url_for('candidates.view', id=candidate.id))
    
    # Запускаем анализ с использованием OpenAI API
    try:
        # Логирование начала анализа
        SystemLog.log(
            event_type="ai_analysis_start",
            description=f"Запущен AI-анализ кандидата ID={candidate.id}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        # Добавляем расшифрованные данные в объект кандидата для передачи в AI API
        candidate.email = candidate_data.email
        candidate.phone = candidate_data.phone
        # Добавляем остальные данные из запроса
        candidate.base_answers = candidate_data.base_answers
        candidate.vacancy_answers = candidate_data.vacancy_answers
        candidate.soft_answers = candidate_data.soft_answers
        candidate.cover_letter = candidate_data.cover_letter
        
        # Логируем данные для диагностики
        current_app.logger.info(f"Данные кандидата для анализа: ID={candidate.id}, Email={candidate.email}, Vacancy ID={candidate.vacancy_id}")
        current_app.logger.info(f"Размер текста резюме: {len(candidate.resume_text) if candidate.resume_text else 0} символов")
        
        # Запрос к OpenAI API
        job_id = request_ai_analysis(candidate)
        
        if job_id:
            # # Создаем уведомление о завершении анализа
            # notification = Notification(
            #     candidate_id=candidate.id,
            #     type="ai_analysis_completed",
            #     message=f"AI-анализ для кандидата {candidate.full_name} завершен",
            #     created_at=datetime.datetime.now()
            # )
            # db.session.add(notification)
            db.session.commit()
            
            # Возвращаем JSON ответ для AJAX или перенаправляем
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'success',
                    'message': 'Анализ кандидата успешно завершен',
                    'job_id': job_id,
                    'redirect_url': url_for('candidates.view', id=candidate.id)
                }), 200
            
            flash('Анализ кандидата успешно завершен', 'success')
        else:
            # Ошибка при запуске анализа
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': 'Произошла ошибка при анализе кандидата. Проверьте настройки API ключа.'}), 500
            
            flash('Произошла ошибка при анализе кандидата. Проверьте настройки API ключа.', 'danger')
            
    except Exception as e:
        # Логирование ошибки
        error_message = f"Ошибка при запуске AI-анализа: {str(e)}"
        current_app.logger.error(error_message)
        
        SystemLog.log(
            event_type="ai_analysis_error",
            description=f"Ошибка при запуске AI-анализа кандидата ID={candidate.id}: {str(e)}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': error_message}), 500
        
        flash(error_message, 'danger')
    
    # Для не-AJAX запросов возвращаем перенаправление
    return redirect(url_for('candidates.view', id=candidate.id))

@candidates_bp.route('/track/<tracking_code>')
@profile_time
def track(tracking_code):
    """Публичная страница для отслеживания статуса кандидата"""
    # Получаем данные кандидата с дешифровкой по tracking_code
    candidate_data = db.session.query(
        Candidate.id,
        Candidate.vacancy_id,
        Candidate.full_name,
        Candidate.base_answers,
        Candidate.tracking_code,
        Candidate.id_c_selection_stage,
        Candidate.interview_date,
        Candidate.created_at,
        func.pgp_sym_decrypt(
            cast(Candidate._email, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('email'),
        func.pgp_sym_decrypt(
            cast(Candidate._phone, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('phone'),
        Vacancy.title.label('vacancy_title'),
        C_Selection_Stage.name.label('status_name'),
        C_Selection_Stage.color_code.label('status_color')
    ).join(
        Vacancy, Candidate.vacancy_id == Vacancy.id
    ).join(
        C_Selection_Stage, Candidate.id_c_selection_stage == C_Selection_Stage.id
    ).filter(
        Candidate.tracking_code == tracking_code
    ).first_or_404()
    
    # Получаем обычную модель для связей (например, notifications)
    candidate = Candidate.query.filter_by(tracking_code=tracking_code).first_or_404()
    
    # Создаем объект с данными для шаблона
    candidate_view = {
        'id': candidate_data.id,
        'full_name': candidate_data.full_name,
        'email': candidate_data.email,
        'phone': candidate_data.phone,
        'vacancy_id': candidate_data.vacancy_id,
        'vacancy': {
            'id': candidate_data.vacancy_id,
            'title': candidate_data.vacancy_title
        },
        'base_answers': candidate_data.base_answers,
        'tracking_code': candidate_data.tracking_code,
        'id_c_selection_stage': candidate_data.id_c_selection_stage,
        'interview_date': candidate_data.interview_date,
        'created_at': candidate_data.created_at,
        'c_candidate_status': {
            'name': candidate_data.status_name,
            'color_code': candidate_data.status_color
        },
        'notifications': candidate.notifications
    }
    
    return render_template(
        'candidates/track.html',
        candidate=candidate_view,
        title='Отслеживание статуса заявки'
    )

@candidates_bp.route('/api/candidates')
@profile_time
@login_required
def api_candidates():
    """API для получения списка кандидатов (для AJAX-запросов)"""
    vacancy_id = request.args.get('vacancy_id', type=int)
    status_id = request.args.get('status_id', type=int)
    
    # Базовый запрос с дешифровкой полей email и phone
    query = db.session.query(
        Candidate.id,
        Candidate.vacancy_id,
        Candidate.full_name,
        func.pgp_sym_decrypt(
            cast(Candidate._email, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('email'),
        func.pgp_sym_decrypt(
            cast(Candidate._phone, sa.LargeBinary),
            current_app.config['ENCRYPTION_KEY'],
            current_app.config.get('ENCRYPTION_OPTIONS', '')
        ).label('phone'),
        Candidate.created_at,
        Candidate.ai_match_percent,
        Candidate.id_c_selection_stage,
        Vacancy.title.label('vacancy_title'),
        C_Selection_Stage.name.label('status_name'),
        C_Selection_Stage.color_code.label('status_color')
    ).join(
        Vacancy, Candidate.vacancy_id == Vacancy.id
    ).join(
        C_Selection_Stage, Candidate.id_c_selection_stage == C_Selection_Stage.id
    ).filter(
        Vacancy.created_by == current_user.id
    )
    
    # Применяем фильтры
    if vacancy_id:
        query = query.filter(Candidate.vacancy_id == vacancy_id)
    
    if status_id:
        query = query.filter(Candidate.id_c_selection_stage == status_id)
    
    # Выполняем запрос
    candidates = query.order_by(Candidate.created_at.desc()).all()
    
    # Преобразуем данные в JSON
    result = []
    for candidate in candidates:
        result.append({
            'id': candidate.id,
            'full_name': candidate.full_name,
            'vacancy': candidate.vacancy_title,
            'status': candidate.status_name if candidate.status_name else 'Заявка подана',
            'status_color': candidate.status_color,
            'created_at': candidate.created_at.strftime('%d.%m.%Y'),
            'ai_match_percent': candidate.ai_match_percent or 0
        })
    
    return jsonify(result)

@candidates_bp.route('/<int:id>/reprocess_resume', methods=['POST'])
@profile_time
@login_required
def reprocess_resume(id):
    """Повторная обработка резюме кандидата с использованием OpenAI API"""
    # Получаем данные кандидата
    candidate = Candidate.query.get_or_404(id)
    vacancy = Vacancy.query.get(candidate.vacancy_id)
    
    # Проверка доступа для HR-менеджера
    if current_user.role == 'hr' and vacancy.created_by != current_user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'Нет доступа к данному кандидату'}), 403
        flash('У вас нет доступа к данному кандидату', 'danger')
        return redirect(url_for('candidates.list'))
    
    # Проверяем наличие резюме
    if not candidate.resume_path or not os.path.exists(candidate.resume_path):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'Резюме не найдено'}), 404
        flash('Резюме не найдено', 'danger')
        return redirect(url_for('candidates.view', id=id))
    
    try:
        # Получаем API ключ из конфигурации или переменных окружения
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            api_key = os.environ.get('OPENAI_API_KEY')
        
        if not api_key or len(api_key.strip()) < 20:
            raise ValueError("OpenAI API ключ не найден или некорректен")
        
        # Инициализируем клиент OpenAI
        client = OpenAI(api_key=api_key)
        
        # Определяем расширение файла
        file_extension = os.path.splitext(candidate.resume_path)[1].lower()
        
        # Обработка в зависимости от типа файла
        if file_extension == '.pdf':
            current_app.logger.info(f"Обрабатываем PDF-файл: {candidate.resume_path}")
            
            # Открываем PDF с помощью PyMuPDF
            pdf_document = fitz.open(candidate.resume_path)
            
            # Подготовка списка для хранения текста со всех страниц
            all_pages_text = []
            
            # Для каждой страницы PDF
            for page_num in range(len(pdf_document)):
                # Получаем страницу
                page = pdf_document[page_num]
                
                # Преобразуем страницу в изображение
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Увеличиваем разрешение для лучшего распознавания
                
                # Конвертируем pixmap в формат, который можно отправить в OpenAI API
                img_data = pix.tobytes("png")
                
                # Кодируем изображение в base64
                img_base64 = base64.b64encode(img_data).decode('utf-8')
                
                # Отправляем запрос к OpenAI API для извлечения текста из изображения
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "Ты специалист по распознаванию текста из документов. Извлеки весь текст из предоставленного изображения страницы резюме, сохраняя структуру и форматирование."
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Это страница {page_num + 1} из {len(pdf_document)} резюме. Извлеки весь текст с этой страницы."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=4096
                )
                
                # Извлекаем распознанный текст из ответа
                page_text = response.choices[0].message.content
                all_pages_text.append(page_text)
            
            # Закрываем документ
            pdf_document.close()
            
            # Объединяем текст со всех страниц
            resume_text = "\n\n".join(all_pages_text)
            
        elif file_extension in ['.jpg', '.jpeg', '.png']:
            current_app.logger.info(f"Обрабатываем изображение: {candidate.resume_path}")
            
            # Для изображений используем прямую отправку в API
            with open(candidate.resume_path, "rb") as file:
                image_data = file.read()
                img_base64 = base64.b64encode(image_data).decode('utf-8')
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "Ты специалист по распознаванию текста из резюме. Извлеки весь текст из предоставленного изображения."
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Извлеки весь текст из этого резюме. Сохрани структуру и форматирование."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/{file_extension[1:]};base64,{img_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=4096
                )
                
                resume_text = response.choices[0].message.content
                
        elif file_extension == '.docx':
            current_app.logger.info(f"Обрабатываем DOCX-файл: {candidate.resume_path}")
            
            # Для DOCX используем python-docx для извлечения текста
            try:
                doc = docx.Document(candidate.resume_path)
                paragraphs = [p.text for p in doc.paragraphs]
                resume_text = "\n".join(paragraphs)
                
                # Если извлечено мало текста, можно конвертировать в изображение и использовать OpenAI
                if len(resume_text) < 100:
                    current_app.logger.warning("Извлечено мало текста из DOCX, попробуем другой подход")
                    # Здесь можно добавить конвертацию DOCX в изображения, если это необходимо
            except Exception as e:
                current_app.logger.error(f"Ошибка при обработке DOCX: {str(e)}")
                raise ValueError(f"Не удалось обработать DOCX-файл: {str(e)}")
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {file_extension}")
        
        # Обновляем текст резюме в базе данных
        candidate.resume_text = resume_text
        candidate.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        current_app.logger.info(f"Текст резюме успешно обновлен с использованием OpenAI API")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'success',
                'message': 'Резюме успешно обработано с помощью OpenAI API',
                'resume_text': resume_text
            })
        
        flash('Резюме успешно обработано с помощью OpenAI API', 'success')
        return redirect(url_for('candidates.view', id=id))
            
    except Exception as e:
        current_app.logger.error(f"Ошибка при обработке резюме через OpenAI API: {str(e)}", exc_info=True)
        db.session.rollback()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': f'Ошибка при обработке резюме: {str(e)}'}), 500
        
        flash(f'Ошибка при обработке резюме: {str(e)}', 'danger')
        return redirect(url_for('candidates.view', id=id))

@candidates_bp.route('/<int:id>/update-status', methods=['POST'])
@login_required
@hr_required
def update_status(id):
    """Обновление статуса кандидата"""
    try:
        candidate = Candidate.query.get_or_404(id)
        new_status_id = request.form.get('status_id', type=int)
        rejection_reason_id = request.form.get('rejection_reason_id', type=int)
        
        if new_status_id:
            candidate.id_c_selection_stage = new_status_id
            
            # Если статус "Отклонен", проверяем наличие причины
            if new_status_id == 5:
                if not rejection_reason_id:
                    return jsonify({
                        'status': 'error',
                        'message': 'Необходимо указать причину отклонения'
                    }), 400
                candidate.id_c_rejection_reason = rejection_reason_id
            else:
                candidate.id_c_rejection_reason = None
        
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка при обновлении статуса кандидата: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Произошла ошибка при обновлении статуса'
        }), 500

@candidates_bp.route('/api/candidates/update-stage', methods=['POST'])
@login_required
def update_candidate_stage():
    """Обновление этапа отбора кандидата через API"""
    data = request.get_json()
    
    if not data or 'candidate_id' not in data or 'stage_id' not in data:
        return jsonify({
            'success': False,
            'message': 'Отсутствуют необходимые данные'
        }), 400
    
    candidate = Candidate.query.get_or_404(data['candidate_id'])
    
    # Проверяем, что кандидат принадлежит вакансии текущего HR
    if not candidate.vacancy or candidate.vacancy.id_hr != current_user.id:
        return jsonify({
            'success': False,
            'message': 'У вас нет доступа к этому кандидату'
        }), 403
    
    stage = C_Selection_Stage.query.get_or_404(data['stage_id'])
    
    # Проверяем, что этап принадлежит текущему HR
    if stage.id_hr != current_user.id:
        return jsonify({
            'success': False,
            'message': 'У вас нет доступа к этому этапу отбора'
        }), 403
    
    # Обновляем этап отбора
    candidate.id_c_selection_stage = stage.id
    
    # Логируем изменение
    log = SystemLog(
        action='change_stage',
        entity_type='candidate',
        entity_id=candidate.id,
        user_id=current_user.id,
        details=f'Изменен этап отбора на "{stage.name}"'
    )
    db.session.add(log)
    
    # Создаем уведомление
    notification = Notification(
        user_id=current_user.id,
        title='Изменение этапа отбора',
        message=f'Кандидат {candidate.full_name} переведен на этап "{stage.name}"',
        type='info'
    )
    db.session.add(notification)
    
    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Этап отбора успешно обновлен'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка при обновлении этапа отбора: {str(e)}'
        }), 500