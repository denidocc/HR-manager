#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import current_user
from app import db
from app.models import Vacancy, Candidate, Notification, SystemLog, User_Selection_Stage
from app.forms.application import ApplicationForm
from app.utils.file_processing import save_resume, extract_text_from_resume
from app.utils.ai_service import request_ai_analysis, process_resume_and_analyze
from app.utils.decorators import profile_time
import uuid
import os
from werkzeug.utils import secure_filename
from wtforms import TextAreaField
from wtforms.validators import DataRequired, Optional
from sqlalchemy import and_, func, cast
import sqlalchemy as sa
import json
from threading import Thread
from app import create_app

public_bp = Blueprint('public_bp', __name__, url_prefix='')

@public_bp.route('/')
@profile_time
def index():
    """Главная страница сайта"""
    # Получаем только активные вакансии для отображения на главной
    active_vacancies_count = Vacancy.query.filter_by(is_active=True).count()
    
    return render_template(
        'public/index.html',
        title='Clever HR: Найдите работу своей мечты'
    )

@public_bp.route('/vacancies')
@profile_time
def vacancies():
    """Список доступных вакансий"""
    # Получаем параметры поиска
    search_query = request.args.get('search', '')
    employment_type = request.args.get('employment_type', '')
    
    # Логирование для отладки
    current_app.logger.info(f"Search parameters: search='{search_query}', employment_type='{employment_type}'")
    
    # Получаем все типы занятости для фильтра
    from app.models import C_Employment_Type
    employment_types = C_Employment_Type.query.all()
    
    # Базовый запрос: только активные вакансии
    query = Vacancy.query.filter_by(is_active=True).order_by(Vacancy.created_at.desc())
    
    # Применяем фильтры, если они указаны
    if search_query:
        # Поиск по названию и описанию
        query = query.filter(
            Vacancy.title.ilike(f'%{search_query}%') | 
            Vacancy.description_tasks.ilike(f'%{search_query}%') |
            Vacancy.ideal_profile.ilike(f'%{search_query}%')
        )
    
    if employment_type and employment_type.isdigit():
        # Используем id напрямую
        employment_type_id = int(employment_type)
        current_app.logger.info(f"Filtering by employment_type_id: {employment_type_id}")
        query = query.filter_by(id_c_employment_type=employment_type_id)
    
    # Получаем результаты
    active_vacancies = query.all()
    current_app.logger.info(f"Found {len(active_vacancies)} matching vacancies")
    
    return render_template(
        'public/vacancies.html',
        vacancies=active_vacancies,
        employment_types=employment_types,
        title='Доступные вакансии'
    )

@public_bp.route('/vacancy/<int:id>')
@profile_time
def vacancy_detail(id):
    """Детальная информация о вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Проверяем, активна ли вакансия
    if not vacancy.is_active:
        flash('Эта вакансия больше не доступна', 'warning')
        return redirect(url_for('public_bp.vacancies'))
    
    return render_template(
        'public/vacancy_detail.html',
        vacancy=vacancy,
        title=vacancy.title
    )

def process_resume_async(candidate_id, resume_path):
    """
    Асинхронная обработка резюме
    """
    try:
        # Создаем новый контекст приложения для асинхронной обработки
        app = create_app()
        
        with app.app_context():
            # Импортируем функцию внутри контекста приложения
            from app.utils.ai_service import process_resume_and_analyze
            
            # Используем функцию для обработки резюме и запуска анализа
            process_resume_and_analyze(candidate_id, resume_path)
        
    except Exception as e:
        # Создаем контекст приложения для логирования ошибки
        app = create_app()
        with app.app_context():
            app.logger.error(f"Ошибка при асинхронной обработке резюме: {str(e)}", exc_info=True)

@public_bp.route('/apply/<int:vacancy_id>', methods=['GET', 'POST'])
@profile_time
def apply(vacancy_id):
    """Обработка заявки на вакансию"""
    vacancy = Vacancy.query.get_or_404(vacancy_id)
    form = ApplicationForm()
    
    if form.validate_on_submit():
        # Проверяем существующую заявку
        existing_application = Candidate.query.filter(
        and_(
                Candidate.vacancy_id == vacancy_id,
            func.pgp_sym_decrypt(
                cast(Candidate._phone, sa.LargeBinary),
                current_app.config['ENCRYPTION_KEY'],
                current_app.config.get('ENCRYPTION_OPTIONS', '')
            ) == form.phone.data, # Разрешаем повторную подачу, если предыдущая была отклонена
        )
    ).first()

        if existing_application:
            flash('Вы уже подавали заявку на эту вакансию с этим номером телефона, пожалуйста, ждите ответа от HR-менеджера', 'warning')
            return redirect(url_for('public_bp.vacancy_detail', id=vacancy_id))

        try:
            # Сохраняем базовую информацию
            tracking_code = str(uuid.uuid4())
            
            # Обрабатываем ответы на вопросы
            vacancy_answers = {}
            if vacancy.questions_json:
                for question in vacancy.questions_json:
                    question_id = str(question['id'])
                    field_name = f'vacancy_question_{question_id}'
                    if hasattr(form, field_name) and getattr(form, field_name).data:
                        vacancy_answers[question_id] = getattr(form, field_name).data
                    elif field_name in request.form and request.form.get(field_name).strip():
                        vacancy_answers[question_id] = request.form.get(field_name).strip()
            
            soft_answers = {}
            if vacancy.soft_questions_json:
                for question in vacancy.soft_questions_json:
                    question_id = str(question['id'])
                    field_name = f'soft_question_{question_id}'
                    if hasattr(form, field_name) and getattr(form, field_name).data:
                        soft_answers[question_id] = getattr(form, field_name).data
                    elif field_name in request.form and request.form.get(field_name).strip():
                        soft_answers[question_id] = request.form.get(field_name).strip()
            
            # Обрабатываем загрузку резюме
            resume_path = None
            if form.resume.data:
                resume_file = form.resume.data
                filename = save_resume(resume_file, tracking_code)
                if filename:
                    resume_path = filename
                    
            # Создаем базовые ответы
            base_answers = {
                "location": form.location.data,
                "experience_years": form.experience_years.data,
                "education": form.education.data,
                "desired_salary": form.desired_salary.data if form.desired_salary.data else None,
                "gender": request.form.get('gender')
            }
            
            # Получаем первый этап отбора для HR-менеджера
            first_stage = User_Selection_Stage.query.filter_by(
                user_id=vacancy.created_by,
                is_active=True
            ).order_by(User_Selection_Stage.order).first()
            
            if not first_stage:
                flash('Ошибка: не найдены этапы отбора для HR-менеджера', 'danger')
                return redirect(url_for('public_bp.vacancy_detail', id=vacancy_id))
            
            # Создаем кандидата
            candidate = Candidate(
                vacancy_id=vacancy.id,
                user_id=vacancy.created_by,
                stage_id=first_stage.stage_id,  # Используем ID этапа из user_selection_stages
                full_name=form.full_name.data,
                email=form.email.data,
                phone=form.phone.data,
                base_answers=base_answers,
                vacancy_answers=vacancy_answers,
                soft_answers=soft_answers,
                cover_letter=form.cover_letter.data,
                resume_path=resume_path,
                resume_text="{}",  # Пустой JSON для начала
                tracking_code=tracking_code,
                gender=request.form.get('gender')
            )
            
            # Сохраняем кандидата
            db.session.add(candidate)
            db.session.commit()
            
            # Создаем уведомление
            notification = Notification(
                candidate_id=candidate.id,
                type="application_received",
                message=f"Ваша заявка на вакансию '{vacancy.title}' принята. Мы свяжемся с вами после рассмотрения."
            )
            db.session.add(notification)
            db.session.commit()
            
            # Логируем создание кандидата
            SystemLog.log(
                event_type="candidate_created",
                description=f"Создан новый кандидат: {candidate.full_name} на вакансию {vacancy.title}",
                ip_address=request.remote_addr
            )
            
            # Запускаем асинхронную обработку резюме и последующий AI-анализ
            if resume_path:
                thread = Thread(target=process_resume_async, args=(candidate.id, resume_path))
                thread.daemon = True
                thread.start()
            
            flash('Ваша заявка успешно отправлена! Используйте код отслеживания для проверки статуса.', 'success')
            return redirect(url_for('public_bp.application_success', tracking_code=tracking_code))
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Ошибка при сохранении заявки: {str(e)}", exc_info=True)
            flash('Произошла ошибка при отправке заявки. Пожалуйста, попробуйте еще раз.', 'danger')
    
    return render_template(
        'public/apply.html',
        vacancy=vacancy,
        form=form,
        title=f'Заявка на вакансию: {vacancy.title}'
    )

@public_bp.route('/application_success/<tracking_code>')
@profile_time
def application_success(tracking_code):
    """Страница успешной подачи заявки"""
    # Пробуем найти кандидата, но не выдаем ошибку, если не найден
    candidate = Candidate.query.filter_by(tracking_code=tracking_code).first()
    
    return render_template(
        'public/application_success.html',
        candidate=candidate,
        tracking_code=tracking_code,
        title='Заявка успешно отправлена'
    )

@public_bp.route('/track')
@profile_time
def track():
    """Страница для отслеживания статуса заявки"""
    return render_template(
        'public/track_form.html',
        title='Отслеживание статуса заявки'
    )

@public_bp.route('/track/result', methods=['POST'])
@profile_time
def track_result():
    """Обработка запроса на отслеживание статуса заявки"""
    tracking_code = request.form.get('tracking_code')
    
    if not tracking_code:
        flash('Пожалуйста, введите код отслеживания', 'warning')
        return redirect(url_for('public_bp.track'))
    
    candidate = Candidate.query.filter_by(tracking_code=tracking_code).first()
    
    if not candidate:
        flash('Заявка с указанным кодом не найдена', 'danger')
        return redirect(url_for('public_bp.track'))
    
    return redirect(url_for('public_bp.candidate_status', tracking_code=tracking_code))

@public_bp.route('/status/<tracking_code>')
@profile_time
def candidate_status(tracking_code):
    """Страница статуса заявки кандидата"""
    # Получаем кандидата с расшифрованными полями и информацией о вакансии
    candidate = Candidate.query.filter_by(tracking_code=tracking_code).first_or_404()
    
    # Загружаем вакансию с этапами отбора
    vacancy = Vacancy.query.get_or_404(candidate.vacancy_id)
    
    # Если у вакансии нет определенных этапов отбора, используем стандартные
    if not vacancy.selection_stages_json:
        # Можно здесь создать стандартные этапы для отображения
        pass
    
    return render_template(
        'public/candidate_status.html',
        candidate=candidate,
        vacancy=vacancy,
        title='Статус заявки'
    )

@public_bp.route('/about')
@profile_time
def about():
    """Страница о компании"""
    return render_template(
        'public/about.html',
        title='О компании'
    )

@public_bp.route('/contact')
@profile_time
def contact():
    """Страница контактов"""
    return render_template(
        'public/contact.html',
        title='Контакты'
    ) 