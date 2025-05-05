#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Vacancy, C_Employment_Type, SystemLog, Candidate
from app.forms.vacancy import VacancyForm
import json

vacancies_bp = Blueprint('vacancies', __name__, url_prefix='/vacancies')

@vacancies_bp.route('/')
@login_required
def index():
    """Список всех вакансий"""
    # Получаем параметры фильтра из запроса
    filter_status = request.args.get('status', 'all')
    
    # Базовый запрос ко всем вакансиям
    query = Vacancy.query
    
    # Применяем фильтры
    if filter_status == 'active':
        query = query.filter(Vacancy.is_active == True)
    elif filter_status == 'archived':
        query = query.filter(Vacancy.is_active == False)
    
    # Сортировка
    vacancies = query.order_by(Vacancy.created_at.desc()).all()
    
    # Словарь для подсчета количества кандидатов по вакансиям
    vacancy_stats = {}
    for vacancy in vacancies:
        count = Candidate.query.filter_by(vacancy_id=vacancy.id).count()
        vacancy_stats[vacancy.id] = count
    
    return render_template(
        'vacancies/index.html', 
        vacancies=vacancies, 
        filter_status=filter_status,
        vacancy_stats=vacancy_stats,
        title='Управление вакансиями'
    )

@vacancies_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Создание новой вакансии"""
    form = VacancyForm()
    
    # Заполняем select с типами занятости
    form.id_c_employment_type.choices = [
        (t.id, t.name) for t in C_Employment_Type.query.all()
    ]
    
    if form.validate_on_submit():
        # Конвертируем строковое представление JSON в Python объекты
        questions = json.loads(form.questions_json.data) if form.questions_json.data else []
        soft_questions = json.loads(form.soft_questions_json.data) if form.soft_questions_json.data else []
        
        # Создаем новую вакансию
        vacancy = Vacancy(
            title=form.title.data,
            id_c_employment_type=form.id_c_employment_type.data,
            description_tasks=form.description_tasks.data,
            description_conditions=form.description_conditions.data,
            ideal_profile=form.ideal_profile.data,
            questions_json=questions,
            soft_questions_json=soft_questions,
            is_active=form.is_active.data,
            created_by=current_user.id
        )
        
        db.session.add(vacancy)
        db.session.commit()
        
        # Логирование
        SystemLog.log(
            event_type="create_vacancy",
            description=f"Создана новая вакансия: {vacancy.title}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        flash('Вакансия успешно создана', 'success')
        return redirect(url_for('vacancies.index'))
    
    return render_template('vacancies/create.html', form=form, title='Создание вакансии')

@vacancies_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Редактирование вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    form = VacancyForm(obj=vacancy)
    
    # Заполняем select с типами занятости
    form.id_c_employment_type.choices = [
        (t.id, t.name) for t in C_Employment_Type.query.all()
    ]
    
    # При GET запросе подготавливаем форму с существующими данными
    if request.method == 'GET':
        form.questions_json.data = json.dumps(vacancy.questions_json)
        form.soft_questions_json.data = json.dumps(vacancy.soft_questions_json)
    
    if form.validate_on_submit():
        # Обновляем поля вакансии
        vacancy.title = form.title.data
        vacancy.id_c_employment_type = form.id_c_employment_type.data
        vacancy.description_tasks = form.description_tasks.data
        vacancy.description_conditions = form.description_conditions.data
        vacancy.ideal_profile = form.ideal_profile.data
        vacancy.questions_json = json.loads(form.questions_json.data) if form.questions_json.data else []
        vacancy.soft_questions_json = json.loads(form.soft_questions_json.data) if form.soft_questions_json.data else []
        vacancy.is_active = form.is_active.data
        
        db.session.commit()
        
        # Логирование
        SystemLog.log(
            event_type="update_vacancy",
            description=f"Обновлена вакансия ID={vacancy.id}: {vacancy.title}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        flash('Вакансия успешно обновлена', 'success')
        return redirect(url_for('vacancies.index'))
    
    return render_template('vacancies/edit.html', form=form, vacancy=vacancy, title='Редактирование вакансии')

@vacancies_bp.route('/<int:id>/toggle_status', methods=['POST'])
@login_required
def toggle_status(id):
    """Изменение статуса активности вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Меняем статус на противоположный
    vacancy.is_active = not vacancy.is_active
    db.session.commit()
    
    status_text = "активна" if vacancy.is_active else "архивирована"
    
    # Логирование
    SystemLog.log(
        event_type="vacancy_status_change",
        description=f"Изменен статус вакансии ID={vacancy.id}: {status_text}",
        user_id=current_user.id,
        ip_address=request.remote_addr
    )
    
    flash(f'Статус вакансии изменен: {status_text}', 'success')
    return redirect(url_for('vacancies.index'))

@vacancies_bp.route('/<int:id>/view')
@login_required
def view(id):
    """Просмотр детальной информации о вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Получаем сопутствующую информацию
    employment_type = C_Employment_Type.query.get(vacancy.id_c_employment_type)
    
    # Количество кандидатов
    candidates_count = Candidate.query.filter_by(vacancy_id=vacancy.id).count()
    
    return render_template(
        'vacancies/view.html', 
        vacancy=vacancy, 
        employment_type=employment_type,
        candidates_count=candidates_count,
        title=vacancy.title
    )

@vacancies_bp.route('/<int:id>/candidates')
@login_required
def candidates(id):
    """Список кандидатов по конкретной вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Получаем параметры фильтрации
    status_filter = request.args.get('status', 'all')
    sort_by = request.args.get('sort', 'date')
    
    # Базовый запрос
    query = Candidate.query.filter_by(vacancy_id=vacancy.id)
    
    # Фильтрация по статусу
    if status_filter != 'all':
        query = query.filter_by(id_c_candidate_status=status_filter)
    
    # Сортировка
    if sort_by == 'date':
        query = query.order_by(Candidate.created_at.desc())
    elif sort_by == 'match':
        query = query.order_by(Candidate.ai_match_percent.desc())
    
    candidates = query.all()
    
    return render_template(
        'vacancies/candidates.html',
        vacancy=vacancy,
        candidates=candidates,
        status_filter=status_filter,
        sort_by=sort_by,
        title=f'Кандидаты на вакансию: {vacancy.title}'
    ) 