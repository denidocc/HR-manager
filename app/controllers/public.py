#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from app import db
from app.models import Vacancy, Candidate, Notification, SystemLog
from app.forms.application import ApplicationForm
from app.utils.file_processing import save_resume, extract_text_from_resume
from app.utils.ai_service import request_ai_analysis
import uuid
import os
from werkzeug.utils import secure_filename

public_bp = Blueprint('public', __name__, url_prefix='')

@public_bp.route('/')
def index():
    """Главная страница сайта"""
    # Получаем только активные вакансии
    active_vacancies = Vacancy.query.filter_by(is_active=True).all()
    
    return render_template(
        'public/index.html',
        vacancies=active_vacancies,
        title='HR-система: Найдите работу своей мечты'
    )

@public_bp.route('/vacancies')
def vacancies():
    """Список доступных вакансий"""
    # Получаем только активные вакансии
    active_vacancies = Vacancy.query.filter_by(is_active=True).all()
    
    return render_template(
        'public/vacancies.html',
        vacancies=active_vacancies,
        title='Доступные вакансии'
    )

@public_bp.route('/vacancy/<int:id>')
def vacancy_detail(id):
    """Детальная информация о вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Проверяем, активна ли вакансия
    if not vacancy.is_active:
        flash('Эта вакансия больше не доступна', 'warning')
        return redirect(url_for('public.vacancies'))
    
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
        return redirect(url_for('public.vacancies'))
    
    form = ApplicationForm()
    
    if form.validate_on_submit():
        # Сохраняем базовую информацию
        tracking_code = str(uuid.uuid4())
        
        candidate = Candidate(
            vacancy_id=vacancy.id,
            full_name=form.full_name.data,
            email=form.email.data,
            phone=form.phone.data,
            base_answers={
                "location": form.location.data,
                "experience_years": form.experience_years.data,
                "education": form.education.data,
                "desired_salary": form.desired_salary.data
            },
            vacancy_answers={},  # Будет заполнено из формы
            soft_answers={},     # Будет заполнено из формы
            id_c_candidate_status=0,  # "Новый" статус
            tracking_code=tracking_code
        )
        
        # Обрабатываем ответы на профессиональные вопросы
        vacancy_answers = {}
        if vacancy.questions_json:
            for question in vacancy.questions_json:
                question_id = str(question['id'])
                field_name = f'vacancy_question_{question_id}'
                if field_name in form.data:
                    vacancy_answers[question_id] = form.data[field_name]
        
        candidate.vacancy_answers = vacancy_answers
        
        # Обрабатываем ответы на soft-skill вопросы
        soft_answers = {}
        if vacancy.soft_questions_json:
            for question in vacancy.soft_questions_json:
                question_id = str(question['id'])
                field_name = f'soft_question_{question_id}'
                if field_name in form.data:
                    soft_answers[question_id] = form.data[field_name]
        
        candidate.soft_answers = soft_answers
        
        # Обрабатываем загрузку резюме
        if form.resume.data:
            resume_file = form.resume.data
            filename = save_resume(resume_file, tracking_code)
            
            if filename:
                candidate.resume_path = filename
                
                # Извлекаем текст из резюме
                resume_text = extract_text_from_resume(filename)
                if resume_text:
                    candidate.resume_text = resume_text
        
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
        
        # Запускаем AI-анализ в фоновом режиме (если есть текст резюме)
        if candidate.resume_text:
            try:
                request_ai_analysis(candidate)
            except Exception as e:
                current_app.logger.error(f"Ошибка при запуске AI-анализа: {str(e)}")
        
        flash('Ваша заявка успешно отправлена! Используйте код отслеживания для проверки статуса.', 'success')
        return redirect(url_for('public.application_success', tracking_code=tracking_code))
    
    return render_template(
        'public/apply.html',
        vacancy=vacancy,
        form=form,
        title=f'Заявка на вакансию: {vacancy.title}'
    )

@public_bp.route('/application_success/<tracking_code>')
def application_success(tracking_code):
    """Страница успешной подачи заявки"""
    candidate = Candidate.query.filter_by(tracking_code=tracking_code).first_or_404()
    
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
        return redirect(url_for('public.track'))
    
    candidate = Candidate.query.filter_by(tracking_code=tracking_code).first()
    
    if not candidate:
        flash('Заявка с указанным кодом не найдена', 'danger')
        return redirect(url_for('public.track'))
    
    return redirect(url_for('candidates.track', tracking_code=tracking_code))

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