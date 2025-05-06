#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import current_user
from app import db
from app.models import Vacancy, Candidate, Notification, SystemLog
from app.forms.application import ApplicationForm
from app.utils.file_processing import save_resume, extract_text_from_resume
from app.utils.ai_service import request_ai_analysis
import uuid
import os
from werkzeug.utils import secure_filename
from wtforms import TextAreaField
from wtforms.validators import DataRequired, Optional

public_bp = Blueprint('public_bp', __name__, url_prefix='')

@public_bp.route('/')
def index():
    """Главная страница сайта"""
    # Получаем только активные вакансии для отображения на главной
    active_vacancies_count = Vacancy.query.filter_by(is_active=True).count()
    
    return render_template(
        'public/index.html',
        title='HRAI: Найдите работу своей мечты'
    )

@public_bp.route('/vacancies')
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
    query = Vacancy.query.filter_by(is_active=True)
    
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

@public_bp.route('/apply/<int:vacancy_id>', methods=['GET', 'POST'])
def apply(vacancy_id):
    """Страница подачи заявки на вакансию"""
    vacancy = Vacancy.query.get_or_404(vacancy_id)
    
    # Проверяем, активна ли вакансия
    if not vacancy.is_active:
        flash('Эта вакансия больше не доступна', 'warning')
        return redirect(url_for('public_bp.vacancies'))
    
    form = ApplicationForm()
    
    # Регистрируем динамические поля для вопросов вакансии
    if vacancy.questions_json:
        for question in vacancy.questions_json:
            question_id = str(question['id'])
            field_name = f'vacancy_question_{question_id}'
            if field_name not in form._fields:
                # Создаем поле для вопроса
                setattr(form, field_name, 
                        TextAreaField(question['text'], 
                                     validators=[DataRequired(message='Это поле обязательно для заполнения')] 
                                     if question.get('required', False) else [Optional()]))
    
    if vacancy.soft_questions_json:
        for question in vacancy.soft_questions_json:
            question_id = str(question['id'])
            field_name = f'soft_question_{question_id}'
            if field_name not in form._fields:
                # Создаем поле для вопроса
                setattr(form, field_name, 
                        TextAreaField(question['text'], 
                                     validators=[DataRequired(message='Это поле обязательно для заполнения')] 
                                     if question.get('required', False) else [Optional()]))
    
    if request.method == 'POST':
        # Добавляем обработку полей, которые могут быть не зарегистрированы в форме
        # (например, если они были добавлены напрямую в шаблоне)
        if vacancy.questions_json:
            for question in vacancy.questions_json:
                question_id = str(question['id'])
                field_name = f'vacancy_question_{question_id}'
                if field_name not in form._fields and field_name in request.form:
                    # Если поле есть в запросе, но не в форме, добавляем его
                    setattr(form, field_name, 
                            TextAreaField(question['text'], 
                                         validators=[DataRequired(message='Это поле обязательно для заполнения')] 
                                         if question.get('required', False) else [Optional()]))
                    # Устанавливаем значение из запроса
                    getattr(form, field_name).data = request.form.get(field_name)
        
        if vacancy.soft_questions_json:
            for question in vacancy.soft_questions_json:
                question_id = str(question['id'])
                field_name = f'soft_question_{question_id}'
                if field_name not in form._fields and field_name in request.form:
                    # Если поле есть в запросе, но не в форме, добавляем его
                    setattr(form, field_name, 
                            TextAreaField(question['text'], 
                                         validators=[DataRequired(message='Это поле обязательно для заполнения')] 
                                         if question.get('required', False) else [Optional()]))
                    # Устанавливаем значение из запроса
                    getattr(form, field_name).data = request.form.get(field_name)
    
    if form.validate_on_submit():
        try:
            # Сохраняем базовую информацию
            tracking_code = str(uuid.uuid4())
            
            # Обрабатываем ответы на профессиональные вопросы
            vacancy_answers = {}
            if vacancy.questions_json:
                for question in vacancy.questions_json:
                    question_id = str(question['id'])
                    field_name = f'vacancy_question_{question_id}'
                    # Проверяем сначала в форме, потом напрямую в request.form
                    if hasattr(form, field_name) and getattr(form, field_name).data:
                        vacancy_answers[question_id] = getattr(form, field_name).data
                    elif field_name in request.form and request.form.get(field_name).strip():
                        vacancy_answers[question_id] = request.form.get(field_name).strip()
            
            # Обрабатываем ответы на soft-skill вопросы
            soft_answers = {}
            if vacancy.soft_questions_json:
                for question in vacancy.soft_questions_json:
                    question_id = str(question['id'])
                    field_name = f'soft_question_{question_id}'
                    # Проверяем сначала в форме, потом напрямую в request.form
                    if hasattr(form, field_name) and getattr(form, field_name).data:
                        soft_answers[question_id] = getattr(form, field_name).data
                    elif field_name in request.form and request.form.get(field_name).strip():
                        soft_answers[question_id] = request.form.get(field_name).strip()
            
            # Обрабатываем загрузку резюме
            if form.resume.data:
                resume_file = form.resume.data
                filename = save_resume(resume_file, tracking_code)
                
                if filename:
                    resume_path = filename
                    
                    # Получаем расширение файла
                    file_extension = os.path.splitext(filename)[1].lower()
                    
                    # Для изображений (jpg, jpeg, png) не пытаемся извлекать текст
                    if file_extension not in ['.jpg', '.jpeg', '.png']:
                        # Извлекаем текст из резюме для других форматов
                        resume_text = extract_text_from_resume(filename)
                        if resume_text:
                            resume_text = resume_text
                    else:
                        # Для изображений просто сохраняем информативное сообщение
                        resume_text = "Файл резюме загружен в формате изображения и доступен для просмотра."
            
            # Создаем кандидата
            candidate = Candidate(
                vacancy_id=vacancy.id,
                full_name=form.full_name.data,
                email=form.email.data,
                phone=form.phone.data,
                base_answers={
                    "location": form.location.data,
                    "experience_years": form.experience_years.data,
                    "education": form.education.data,
                    "desired_salary": form.desired_salary.data if form.desired_salary.data else None
                },
                vacancy_answers=vacancy_answers,
                soft_answers=soft_answers,
                cover_letter=form.cover_letter.data,
                resume_path=resume_path,
                id_c_candidate_status=1  # Статус "Новая заявка"
            )
            
            # Сохраняем кандидата
            db.session.add(candidate)
            db.session.commit()
            
            # Создаем уведомление о новой заявке
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
            
            # Запускаем AI-анализ в фоновом режиме, если настроено
            if hasattr(candidate, 'resume_text') and candidate.resume_text and 'ai_analysis' in current_app.config.get('ENABLED_FEATURES', []):
                try:
                    request_ai_analysis(candidate)
                except Exception as e:
                    current_app.logger.error(f"Ошибка при запуске AI-анализа: {str(e)}")
            
            flash('Ваша заявка успешно отправлена! Используйте код отслеживания для проверки статуса.', 'success')
            return redirect(url_for('public_bp.application_success', tracking_code=tracking_code))
        
        except Exception as e:
            # Откатываем транзакцию в случае ошибки
            db.session.rollback()
            current_app.logger.error(f"Ошибка при сохранении заявки: {str(e)}")
            flash('Произошла ошибка при отправке заявки. Пожалуйста, попробуйте еще раз.', 'danger')
    
    # Если есть ошибки валидации, выводим их
    if form.errors:
        # Выводим только общую ошибку, без деталей по каждому полю
        flash('Пожалуйста, исправьте ошибки в форме и попробуйте снова.', 'danger')
    
    return render_template(
        'public/apply.html',
        vacancy=vacancy,
        form=form,
        title=f'Заявка на вакансию: {vacancy.title}'
    )

@public_bp.route('/application_success/<tracking_code>')
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
def track():
    """Страница для отслеживания статуса заявки"""
    return render_template(
        'public/track_form.html',
        title='Отслеживание статуса заявки'
    )

@public_bp.route('/track/result', methods=['POST'])
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
def candidate_status(tracking_code):
    """Страница статуса заявки кандидата"""
    candidate = Candidate.query.filter_by(tracking_code=tracking_code).first_or_404()
    
    return render_template(
        'public/candidate_status.html',
        candidate=candidate,
        title='Статус заявки'
    )

@public_bp.route('/about')
def about():
    """Страница о компании"""
    return render_template(
        'public/about.html',
        title='О компании'
    )

@public_bp.route('/contact')
def contact():
    """Страница контактов"""
    return render_template(
        'public/contact.html',
        title='Контакты'
    ) 