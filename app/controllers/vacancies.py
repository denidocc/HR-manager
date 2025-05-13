#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Vacancy, C_Employment_Type, SystemLog, Candidate
from app.forms.vacancy import VacancyForm
import json
import logging
import traceback
from app.utils.decorators import profile_time

# Получаем логгер
logger = logging.getLogger(__name__)

vacancies_bp = Blueprint('vacancies', __name__, url_prefix='/vacancies')

@vacancies_bp.route('/')
@profile_time
@login_required
def index():
    """Список всех вакансий"""
    # Получаем параметры фильтра из запроса
    filter_status = request.args.get('status', 'all')
    
    # Базовый запрос только к вакансиям текущего HR-менеджера
    query = Vacancy.query.filter_by(created_by=current_user.id)
    
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
        title='Мои вакансии'
    )

@vacancies_bp.route('/create', methods=['GET', 'POST'])
@profile_time
@login_required
def create():
    """Создание новой вакансии"""
    form = VacancyForm()
    
    # Заполняем select с типами занятости
    form.id_c_employment_type.choices = [
        (0, 'Выберите тип занятости')
    ] + [(t.id, t.name) for t in C_Employment_Type.query.all()]
    
    if request.method == 'POST':
        logger.info("Получен POST-запрос для создания вакансии")
        logger.info(f"Список всех полей формы: {list(request.form.keys())}")
        
        # Получаем данные JSON из формы
        questions_json = request.form.get('questions_json', '[]')
        soft_questions_json = request.form.get('soft_questions_json', '[]')
        
        # Логируем для отладки
        logger.info(f"Получены данные вопросов из запроса: {questions_json}")
        logger.info(f"Получены данные soft-вопросов из запроса: {soft_questions_json}")
        logger.info(f"Form data для вопросов: {form.questions_json.data}")
        logger.info(f"Form data для soft-вопросов: {form.soft_questions_json.data}")
        
        # Если форма не валидна, логируем ошибки и отображаем форму снова
        if not form.validate_on_submit():
            logger.warning(f"Форма не прошла валидацию. Ошибки: {form.errors}")
            return render_template('vacancies/create.html', form=form, title='Создание вакансии')
            
        # Валидация выбора типа занятости
        if form.id_c_employment_type.data == 0:
            form.id_c_employment_type.errors.append('Выберите тип занятости')
            return render_template('vacancies/create.html', form=form, title='Создание вакансии')
        
        try:
            # Конвертируем строковое представление JSON в Python объекты
            if not questions_json:
                logger.warning("Поле questions_json пустое, использую пустой список")
                questions = []
            else:
                questions = json.loads(questions_json)
                logger.info(f"Преобразованы вопросы: {questions}")
                
            if not soft_questions_json:
                logger.warning("Поле soft_questions_json пустое, использую пустой список")
                soft_questions = []
            else:
                soft_questions = json.loads(soft_questions_json)
                logger.info(f"Преобразованы soft-вопросы: {soft_questions}")
                
            # Проверяем формат данных
            if not isinstance(questions, list):
                logger.error(f"Вопросы не являются списком: {type(questions)}")
                questions = []
                
            if not isinstance(soft_questions, list):
                logger.error(f"Soft-вопросы не являются списком: {type(soft_questions)}")
                soft_questions = []
                
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
            
            logger.info(f"Создается вакансия с вопросами: {vacancy.questions_json}")
            logger.info(f"Создается вакансия с soft-вопросами: {vacancy.soft_questions_json}")
            
            db.session.add(vacancy)
            db.session.commit()
            
            logger.info(f"Вакансия успешно создана с ID: {vacancy.id}")
            logger.info(f"Сохраненные вопросы: {vacancy.questions_json}")
            logger.info(f"Сохраненные soft-вопросы: {vacancy.soft_questions_json}")
            
            # Логирование
            SystemLog.log(
                event_type="create_vacancy",
                description=f"Создана новая вакансия: {vacancy.title}",
                user_id=current_user.id,
                ip_address=request.remote_addr
            )
            
            flash('Вакансия успешно создана', 'success')
            return redirect(url_for('vacancies.index'))
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON: {e}")
            logger.error(f"Строка, вызвавшая ошибку: {questions_json if 'questions_json' in locals() else 'questions_json не определен'}")
            flash(f'Ошибка в данных вопросов. Пожалуйста, проверьте и попробуйте снова.', 'danger')
            return render_template('vacancies/create.html', form=form, title='Создание вакансии')
        except Exception as e:
            logger.error(f"Непредвиденная ошибка: {e}")
            logger.error(traceback.format_exc())
            flash(f'Произошла ошибка при создании вакансии: {str(e)}', 'danger')
            return render_template('vacancies/create.html', form=form, title='Создание вакансии')
    
    return render_template('vacancies/create.html', form=form, title='Создание вакансии')

@vacancies_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@profile_time
@login_required
def edit(id):
    """Редактирование вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Проверяем, принадлежит ли вакансия текущему пользователю
    if vacancy.created_by != current_user.id:
        flash('У вас нет доступа к редактированию этой вакансии', 'danger')
        return redirect(url_for('vacancies.index'))
    
    form = VacancyForm(obj=vacancy)
    
    # Заполняем select с типами занятости
    form.id_c_employment_type.choices = [
        (0, 'Выберите тип занятости')
    ] + [(t.id, t.name) for t in C_Employment_Type.query.all()]
    
    # При GET запросе подготавливаем форму с существующими данными
    if request.method == 'GET':
        try:
            # Проверим и преобразуем данные перед передачей в форму
            if vacancy.questions_json is None:
                vacancy.questions_json = []
            if vacancy.soft_questions_json is None:
                vacancy.soft_questions_json = []
                
            logger.info(f"Данные вопросов из БД: {vacancy.questions_json}")
            logger.info(f"Данные soft-вопросов из БД: {vacancy.soft_questions_json}")
            
            # Проверим, что данные являются списками
            if not isinstance(vacancy.questions_json, list):
                logger.warning(f"Данные вопросов не являются списком: {type(vacancy.questions_json)}")
                vacancy.questions_json = []
                
            if not isinstance(vacancy.soft_questions_json, list):
                logger.warning(f"Данные soft-вопросов не являются списком: {type(vacancy.soft_questions_json)}")
                vacancy.soft_questions_json = []
            
            # Проверим содержат ли вопросы текст
            has_questions_without_text = False
            if isinstance(vacancy.questions_json, list):
                for i, q in enumerate(vacancy.questions_json):
                    if isinstance(q, dict) and (not q.get('text') or q.get('text') == ''):
                        logger.warning(f"Вопрос {i+1} не имеет текста: {q}")
                        has_questions_without_text = True
            
            # Сериализуем в JSON - используем dumps с обеспечением корректного экранирования
            questions_json = json.dumps(vacancy.questions_json, ensure_ascii=False)
            soft_questions_json = json.dumps(vacancy.soft_questions_json, ensure_ascii=False)
            
            # Вместо изменения form.data напрямую, мы передадим эти данные в шаблон
            form.questions_json.data = questions_json
            form.soft_questions_json.data = soft_questions_json
            
            logger.info(f"GET: Сериализованные вопросы: {questions_json}")
            logger.info(f"GET: Сериализованные soft-вопросы: {soft_questions_json}")
            
            if has_questions_without_text:
                logger.warning("Обнаружены вопросы без текста!")
                flash('Некоторые вопросы не имеют текста. Пожалуйста, проверьте и заполните их.', 'warning')
                
        except Exception as e:
            logger.error(f"Ошибка при подготовке данных формы: {e}")
            logger.error(traceback.format_exc())
    
    if request.method == 'POST':
        logger.info(f"POST: Редактирование вакансии ID={id}")
        logger.info(f"POST: Список всех полей формы: {list(request.form.keys())}")
        
        # Если форма не валидна, логируем ошибки
        if not form.validate_on_submit():
            logger.warning(f"Форма не прошла валидацию. Ошибки: {form.errors}")
            return render_template('vacancies/edit.html', form=form, vacancy=vacancy, title='Редактирование вакансии')
            
        # Валидация выбора типа занятости
        if form.id_c_employment_type.data == 0:
            form.id_c_employment_type.errors.append('Выберите тип занятости')
            return render_template('vacancies/edit.html', form=form, vacancy=vacancy, title='Редактирование вакансии')
        
        # Получаем данные JSON из формы
        questions_json = request.form.get('questions_json', '[]')
        soft_questions_json = request.form.get('soft_questions_json', '[]')
        
        # Логируем для отладки
        logger.info(f"POST: Получены данные вопросов: {questions_json}")
        logger.info(f"POST: Получены данные soft-вопросов: {soft_questions_json}")
        
        try:
            # Конвертируем JSON в объекты Python
            if not questions_json or questions_json.strip() == '':
                logger.warning("Поле questions_json пустое, использую пустой список")
                questions = []
            else:
                questions = json.loads(questions_json)
                logger.info(f"POST: Преобразованы вопросы: {questions}")
                
            if not soft_questions_json or soft_questions_json.strip() == '':
                logger.warning("Поле soft_questions_json пустое, использую пустой список")
                soft_questions = []
            else:
                soft_questions = json.loads(soft_questions_json)
                logger.info(f"POST: Преобразованы soft-вопросы: {soft_questions}")
            
            # Проверяем формат данных вопросов
            if not isinstance(questions, list):
                logger.error(f"Вопросы не являются списком: {type(questions)}")
                questions = []
                
            if not isinstance(soft_questions, list):
                logger.error(f"Soft-вопросы не являются списком: {type(soft_questions)}")
                soft_questions = []
                
            # Обновляем данные вакансии
            vacancy.title = form.title.data
            vacancy.id_c_employment_type = form.id_c_employment_type.data
            vacancy.description_tasks = form.description_tasks.data
            vacancy.description_conditions = form.description_conditions.data
            vacancy.ideal_profile = form.ideal_profile.data
            vacancy.questions_json = questions
            vacancy.soft_questions_json = soft_questions
            vacancy.is_active = form.is_active.data
            
            logger.info(f"POST: Обновляем вакансию с вопросами: {vacancy.questions_json}")
            logger.info(f"POST: Обновляем вакансию с soft-вопросами: {vacancy.soft_questions_json}")
            
            db.session.commit()
            
            logger.info(f"Вакансия успешно обновлена: ID={vacancy.id}")
            logger.info(f"Сохраненные вопросы: {vacancy.questions_json}")
            logger.info(f"Сохраненные soft-вопросы: {vacancy.soft_questions_json}")
            
            # Логирование
            SystemLog.log(
                event_type="edit_vacancy",
                description=f"Отредактирована вакансия: {vacancy.title}",
                user_id=current_user.id,
                ip_address=request.remote_addr
            )
            
            flash('Вакансия успешно обновлена', 'success')
            return redirect(url_for('vacancies.index'))
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON: {e}")
            logger.error(f"Строка, вызвавшая ошибку: {questions_json if 'questions_json' in locals() else 'questions_json не определен'}")
            flash(f'Ошибка в данных вопросов. Пожалуйста, проверьте и попробуйте снова.', 'danger')
            return render_template('vacancies/edit.html', form=form, vacancy=vacancy, title='Редактирование вакансии')
        except Exception as e:
            logger.error(f"Непредвиденная ошибка: {e}")
            logger.error(traceback.format_exc())
            flash(f'Произошла ошибка при обновлении вакансии: {str(e)}', 'danger')
            return render_template('vacancies/edit.html', form=form, vacancy=vacancy, title='Редактирование вакансии')
    
    return render_template('vacancies/edit.html', form=form, vacancy=vacancy, title='Редактирование вакансии')

@vacancies_bp.route('/<int:id>/toggle_status', methods=['POST'])
@profile_time
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
@profile_time
@login_required
def view(id):
    """Просмотр детальной информации о вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Проверяем, принадлежит ли вакансия текущему пользователю
    if vacancy.created_by != current_user.id:
        flash('У вас нет доступа к просмотру этой вакансии', 'danger')
        return redirect(url_for('vacancies.index'))
    
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
@profile_time
@login_required
def candidates(id):
    """Список кандидатов по конкретной вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Проверяем, принадлежит ли вакансия текущему пользователю
    if vacancy.created_by != current_user.id:
        flash('У вас нет доступа к кандидатам этой вакансии', 'danger')
        return redirect(url_for('vacancies.index'))
    
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

@vacancies_bp.route('/<int:id>/archive', methods=['POST'])
@profile_time
@login_required
def archive(id):
    """Архивация или восстановление вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Проверяем, принадлежит ли вакансия текущему пользователю
    if vacancy.created_by != current_user.id:
        flash('У вас нет доступа к архивации этой вакансии', 'danger')
        return redirect(url_for('vacancies.index'))
    
    # Инвертируем текущий статус
    vacancy.is_active = not vacancy.is_active
    
    # Сохраняем изменения
    db.session.commit()
    
    # Логирование
    action = "восстановление" if vacancy.is_active else "архивация"
    SystemLog.log(
        event_type=f"vacancy_{action}",
        description=f"{action.capitalize()} вакансии ID={vacancy.id}: {vacancy.title}",
        user_id=current_user.id,
        ip_address=request.remote_addr
    )
    
    flash(f'Вакансия успешно {"восстановлена" if vacancy.is_active else "архивирована"}', 'success')
    return redirect(url_for('vacancies.index')) 