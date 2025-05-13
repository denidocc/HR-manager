#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_from_directory, abort, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Candidate, Vacancy, C_Candidate_Status, SystemLog, Notification
from app.forms.candidate import CandidateCommentForm, CandidateStatusForm
from app.utils.ai_service import request_ai_analysis
from app.utils.email_service import send_status_change_notification
from app.utils.decorators import profile_time
import os
from werkzeug.utils import secure_filename
import datetime
import json
import logging
from sqlalchemy import desc, func, cast
import sqlalchemy as sa

# Получаем логгер
logger = logging.getLogger(__name__)

candidates_bp = Blueprint('candidates', __name__, url_prefix='/candidates')

@candidates_bp.route('/')
@profile_time
@login_required
def index():
    """Список всех кандидатов HR-менеджера"""
    # Получаем параметры фильтра
    vacancy_id = request.args.get('vacancy_id', type=int)
    status_id = request.args.get('status_id', type=int)
    sort_by = request.args.get('sort_by', 'date')
    
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
        Candidate.id_c_candidate_status,
        Vacancy.title.label('vacancy_title'),
        Vacancy.id.label('vacancy_id'),
        C_Candidate_Status.name.label('status_name'),
        C_Candidate_Status.color_code.label('status_color')
    ).join(
        Vacancy, Candidate.vacancy_id == Vacancy.id
    ).join(
        C_Candidate_Status, Candidate.id_c_candidate_status == C_Candidate_Status.id
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
    
    # Выполняем запрос
    candidates_data = query.all()
    
    # Преобразуем данные в список объектов для шаблона
    candidates = []
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
            'id_c_candidate_status': c.id_c_candidate_status,
            'c_candidate_status': {
                'name': c.status_name,
                'color_code': c.status_color
            }
        }
        candidates.append(candidate)
    
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
        Candidate.interview_date,
        Candidate.hr_comment,
        Candidate.created_at,
        Candidate.updated_at,
        Candidate.tracking_code,
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
        Candidate.id_c_candidate_status,
        Vacancy.title.label('vacancy_title')
    ).join(
        Vacancy, Candidate.vacancy_id == Vacancy.id
    ).filter(Candidate.id == id).first_or_404()
    
    # Получаем обычную модель кандидата для связей
    candidate = Candidate.query.get_or_404(id)
    
    # Получаем данные о вакансии и статусе
    vacancy = Vacancy.query.get(candidate_data.vacancy_id)
    status = C_Candidate_Status.query.get(candidate_data.id_c_candidate_status)
    
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
        'interview_date': candidate_data.interview_date,
        'hr_comment': candidate_data.hr_comment,
        'created_at': candidate_data.created_at,
        'updated_at': candidate_data.updated_at,
        'tracking_code': candidate_data.tracking_code,
        'c_candidate_status': status,
        'id_c_candidate_status': candidate_data.id_c_candidate_status,
        'notifications': candidate.notifications  # Берем из оригинальной модели
    }
    
    # Проверяем, принадлежит ли вакансия текущему HR-менеджеру
    if vacancy.created_by != current_user.id:
        flash('У вас нет доступа к просмотру этого кандидата', 'danger')
        return redirect(url_for('candidates.index'))
    
    # Получаем статусы для формы изменения статуса
    statuses = C_Candidate_Status.query.all()
    
    # Определяем путь к файлу резюме (если есть)
    resume_file_url = None
    if candidate_data.resume_path:
        resume_file_url = url_for('files.download_file', filename=os.path.basename(candidate_data.resume_path))
    
    return render_template(
        'candidates/view.html',
        candidate=candidate_view,
        statuses=statuses,
        resume_file_url=resume_file_url,
        title=f'Кандидат: {candidate_data.full_name}'
    )

@candidates_bp.route('/<int:id>/change_status', methods=['POST'])
@profile_time
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
            interview_date = datetime.datetime.strptime(interview_date_str, '%Y-%m-%dT%H:%M')
            candidate.interview_date = interview_date
        except ValueError:
            flash('Некорректный формат даты собеседования', 'warning')
    
    # Создаем уведомление о смене статуса
    notification_type = "status_update"
    message = f"Статус вашей заявки на вакансию '{candidate.vacancy.title}' изменен на '{status.name}'."
    
    # Специальные типы уведомлений в зависимости от статуса
    if new_status_id == 2:  # Назначено интервью
        notification_type = "interview_invitation"
        date_str = candidate.interview_date.strftime('%d.%m.%Y %H:%M') if candidate.interview_date else "будет согласована дополнительно"
        message = f"Приглашаем вас на собеседование по вакансии '{candidate.vacancy.title}'. Дата: {date_str}."
    elif new_status_id == 5:  # Отказ (предполагаем, что ID=5 для отказа)
        notification_type = "rejection"
        message = f"К сожалению, ваша кандидатура на вакансию '{candidate.vacancy.title}' была отклонена. Благодарим за интерес к нашей компании."
    elif new_status_id == 4:  # Предложение о работе (предполагаем, что ID=4 для предложения)
        notification_type = "offer"
        message = f"Поздравляем! Вам сделано предложение о работе на позицию '{candidate.vacancy.title}'. Ожидаем вашего ответа."
    
    # Создаем новое уведомление
    notification = Notification(
        candidate_id=candidate.id,
        type=notification_type,
        message=message,
        created_at=datetime.datetime.now()
    )
    db.session.add(notification)
    
    # Сохраняем изменения в БД
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
        download_name=f"resume_{candidate.full_name}_{datetime.datetime.now().strftime('%Y%m%d')}{os.path.splitext(filename)[1]}"
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
        Candidate.id_c_candidate_status,
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
        C_Candidate_Status.name.label('status_name'),
        C_Candidate_Status.color_code.label('status_color')
    ).join(
        Vacancy, Candidate.vacancy_id == Vacancy.id
    ).join(
        C_Candidate_Status, Candidate.id_c_candidate_status == C_Candidate_Status.id
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
        'id_c_candidate_status': candidate_data.id_c_candidate_status,
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
        Candidate.id_c_candidate_status,
        Vacancy.title.label('vacancy_title'),
        C_Candidate_Status.name.label('status_name'),
        C_Candidate_Status.color_code.label('status_color')
    ).join(
        Vacancy, Candidate.vacancy_id == Vacancy.id
    ).join(
        C_Candidate_Status, Candidate.id_c_candidate_status == C_Candidate_Status.id
    ).filter(
        Vacancy.created_by == current_user.id
    )
    
    # Применяем фильтры
    if vacancy_id:
        query = query.filter(Candidate.vacancy_id == vacancy_id)
    
    if status_id:
        query = query.filter(Candidate.id_c_candidate_status == status_id)
    
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