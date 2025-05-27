#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Vacancy, C_Employment_Type, SystemLog, Candidate, User_Selection_Stage
from app.forms.vacancy import VacancyForm, VacancyAIGeneratorForm
from app.utils.ai_service import generate_vacancy_with_ai
import json
import logging
import traceback
from app.utils.decorators import profile_time
from datetime import datetime, timezone
import openai
from flask import current_app

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
        ('', 'Выберите тип занятости')
    ] + [(t.id, t.name) for t in C_Employment_Type.query.all() if t.id != 0]
    
    if form.validate_on_submit():
        try:
            # Получаем данные из формы
            questions_json = request.form.get('questions_json', '[]')
            soft_questions_json = request.form.get('soft_questions_json', '[]')
            
            current_app.logger.info("=== Начало обработки данных формы ===")
            current_app.logger.info(f"Все данные формы: {dict(request.form)}")
            current_app.logger.info(f"questions_json: {questions_json}")
            current_app.logger.info(f"soft_questions_json: {soft_questions_json}")
            
            # Проверяем и парсим JSON данные
            try:
                questions = json.loads(questions_json) if questions_json and questions_json != '[]' else []
                soft_questions = json.loads(soft_questions_json) if soft_questions_json and soft_questions_json != '[]' else []
                
                current_app.logger.info("=== Распарсенные данные ===")
                current_app.logger.info(f"questions: {json.dumps(questions, ensure_ascii=False)}")
                current_app.logger.info(f"soft_questions: {json.dumps(soft_questions, ensure_ascii=False)}")
                
                # Проверяем, что данные являются списками
                if not isinstance(questions, list):
                    current_app.logger.warning(f"questions не является списком: {type(questions)}")
                    questions = []
                if not isinstance(soft_questions, list):
                    current_app.logger.warning(f"soft_questions не является списком: {type(soft_questions)}")
                    soft_questions = []
                
                # Проверяем формат каждого вопроса
                validated_questions = []
                for q in questions:
                    if isinstance(q, dict) and 'text' in q:
                        validated_questions.append({
                            'id': len(validated_questions) + 1,
                            'text': q['text'],
                            'type': q.get('type', 'text'),
                            'required': q.get('required', True)
                        })
                
                validated_soft_questions = []
                for q in soft_questions:
                    if isinstance(q, dict) and 'text' in q:
                        validated_soft_questions.append({
                            'id': len(validated_soft_questions) + 1,
                            'text': q['text'],
                            'type': q.get('type', 'text'),
                            'required': q.get('required', True)
                        })
                
                current_app.logger.info("=== Валидированные данные ===")
                current_app.logger.info(f"validated_questions: {json.dumps(validated_questions, ensure_ascii=False)}")
                current_app.logger.info(f"validated_soft_questions: {json.dumps(validated_soft_questions, ensure_ascii=False)}")
                
            except json.JSONDecodeError as e:
                current_app.logger.error(f'Ошибка при парсинге JSON: {str(e)}')
                current_app.logger.error(f'Проблемные данные:')
                current_app.logger.error(f'questions_json: {questions_json}')
                current_app.logger.error(f'soft_questions_json: {soft_questions_json}')
                flash('Ошибка при обработке вопросов', 'error')
                return render_template('vacancies/create.html', form=form)
            
            # Получаем этапы отбора для текущего HR
            user_stages = User_Selection_Stage.query.filter_by(
                user_id=current_user.id,
                is_active=True
            ).order_by(User_Selection_Stage.order).all()
            
            # Преобразуем этапы в JSON формат
            selection_stages = []
            for stage in user_stages:
                selection_stages.append({
                    'id': stage.stage_id,
                    'name': stage.selection_stage.name,
                    'description': stage.selection_stage.description,
                    'order': stage.order,
                    'color': stage.selection_stage.color
                })
            
            # Создаем новую вакансию
            is_ai_generated = bool(form.is_ai_generated.data) if hasattr(form, 'is_ai_generated') and form.is_ai_generated.data else False
            
            vacancy = Vacancy(
                title=form.title.data,
                id_c_employment_type=form.id_c_employment_type.data,
                description_tasks=form.description_tasks.data,
                description_conditions=form.description_conditions.data,
                ideal_profile=form.ideal_profile.data,
                questions_json=validated_questions,
                soft_questions_json=validated_soft_questions,
                selection_stages_json=selection_stages,
                is_active=form.is_active.data,
                created_by=current_user.id,
                # Обработка AI-метаданных
                is_ai_generated=is_ai_generated,
                ai_generation_date=datetime.now(timezone.utc) if is_ai_generated else None,
                ai_generation_prompt=form.ai_generation_prompt.data if hasattr(form, 'ai_generation_prompt') and is_ai_generated else None,
                ai_generation_metadata=json.loads(form.ai_generation_metadata.data) if hasattr(form, 'ai_generation_metadata') and form.ai_generation_metadata.data and is_ai_generated else {}
            )
            
            current_app.logger.info("=== Данные вакансии перед сохранением ===")
            current_app.logger.info(f"questions_json: {json.dumps(vacancy.questions_json, ensure_ascii=False)}")
            current_app.logger.info(f"soft_questions_json: {json.dumps(vacancy.soft_questions_json, ensure_ascii=False)}")
            current_app.logger.info(f"selection_stages_json: {json.dumps(vacancy.selection_stages_json, ensure_ascii=False)}")
            current_app.logger.info(f"AI метаданные: is_ai_generated={vacancy.is_ai_generated}, date={vacancy.ai_generation_date}, prompt={vacancy.ai_generation_prompt}, metadata={vacancy.ai_generation_metadata}")
            
            db.session.add(vacancy)
            db.session.commit()
            
            current_app.logger.info("=== Вакансия успешно создана ===")
            current_app.logger.info(f"ID вакансии: {vacancy.id}")
            current_app.logger.info(f"Сохраненные вопросы:")
            current_app.logger.info(f"questions_json: {json.dumps(vacancy.questions_json, ensure_ascii=False)}")
            current_app.logger.info(f"soft_questions_json: {json.dumps(vacancy.soft_questions_json, ensure_ascii=False)}")
            current_app.logger.info(f"selection_stages_json: {json.dumps(vacancy.selection_stages_json, ensure_ascii=False)}")
            
            flash('Вакансия успешно создана', 'success')
            return redirect(url_for('vacancies.view', id=vacancy.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Ошибка при создании вакансии: {str(e)}')
            current_app.logger.error(traceback.format_exc())
            flash('Произошла ошибка при создании вакансии', 'error')
    
    return render_template('vacancies/create.html', form=form)

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
        ('', 'Выберите тип занятости')
    ] + [(t.id, t.name) for t in C_Employment_Type.query.all() if t.id != 0]
    
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
            
            # Сериализуем в JSON - используем dumps с обеспечением корректного экранирования
            questions_json = json.dumps(vacancy.questions_json, ensure_ascii=False)
            soft_questions_json = json.dumps(vacancy.soft_questions_json, ensure_ascii=False)
            
            # Вместо изменения form.data напрямую, мы передадим эти данные в шаблон
            form.questions_json.data = questions_json
            form.soft_questions_json.data = soft_questions_json
            
            logger.info(f"GET: Сериализованные вопросы: {questions_json}")
            logger.info(f"GET: Сериализованные soft-вопросы: {soft_questions_json}")
            
        except Exception as e:
            logger.error(f"Ошибка при подготовке данных формы: {e}")
            logger.error(traceback.format_exc())
            # В случае ошибки используем пустые списки
            form.questions_json.data = '[]'
            form.soft_questions_json.data = '[]'
    
    if request.method == 'POST':
        logger.info(f"POST: Редактирование вакансии ID={id}")
        logger.info(f"POST: Список всех полей формы: {list(request.form.keys())}")
        
        # Получаем данные JSON из формы
        questions_json = request.form.get('questions_json', '[]')
        soft_questions_json = request.form.get('soft_questions_json', '[]')
        
        logger.info(f"POST: Получены данные вопросов: {questions_json}")
        logger.info(f"POST: Получены данные soft-вопросов: {soft_questions_json}")
        
        try:
            # Конвертируем JSON в объекты Python
            questions = json.loads(questions_json) if questions_json else []
            soft_questions = json.loads(soft_questions_json) if soft_questions_json else []
            
            logger.info(f"POST: Преобразованы вопросы: {questions}")
            logger.info(f"POST: Преобразованы soft-вопросы: {soft_questions}")
            
            # Обновляем данные вакансии
            vacancy.title = form.title.data
            vacancy.id_c_employment_type = form.id_c_employment_type.data
            vacancy.description_tasks = form.description_tasks.data
            vacancy.description_conditions = form.description_conditions.data
            vacancy.ideal_profile = form.ideal_profile.data
            vacancy.questions_json = questions
            vacancy.soft_questions_json = soft_questions
            vacancy.is_active = form.is_active.data
            
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
            
            # Если это AJAX запрос, возвращаем JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'success',
                    'message': 'Вакансия успешно обновлена',
                    'redirect': url_for('vacancies.index')
                })
            
            flash('Вакансия успешно обновлена', 'success')
            return redirect(url_for('vacancies.index'))
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'error',
                    'message': 'Ошибка в данных вопросов'
                }), 400
            
            flash('Ошибка в данных вопросов', 'danger')
            return render_template('vacancies/edit.html', form=form, vacancy=vacancy, title='Редактирование вакансии')
            
        except Exception as e:
            logger.error(f"Непредвиденная ошибка: {e}")
            logger.error(traceback.format_exc())
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                }), 500
            
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
        query = query.filter_by(stage_id=status_filter)
    
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
    """Архивация вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Проверяем, принадлежит ли вакансия текущему пользователю
    if vacancy.created_by != current_user.id:
        flash('У вас нет доступа к архивации этой вакансии', 'danger')
        return redirect(url_for('vacancies.index'))
    
    try:
        # Меняем статус на архивный
        vacancy.is_active = False
        db.session.commit()
        
        # Логирование
        SystemLog.log(
            event_type="archive_vacancy",
            description=f"Вакансия архивирована: {vacancy.title}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
        
        flash('Вакансия успешно архивирована', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Ошибка при архивации вакансии: {str(e)}")
        flash('Произошла ошибка при архивации вакансии', 'danger')
    
    return redirect(url_for('vacancies.index'))

@vacancies_bp.route('/generate_with_ai', methods=['POST'])
@profile_time
@login_required
def generate_with_ai():
    """Генерация вакансии с помощью AI"""
    try:
        # Получаем данные из формы
        title = request.form.get('title')
        employment_type = request.form.get('id_c_employment_type')
        description_tasks = request.form.get('description_tasks')
        description_conditions = request.form.get('description_conditions')
        
        current_app.logger.info(f"Отправляем запрос к OpenAI API для генерации вакансии: {title}")
        
        # Генерируем вакансию с помощью AI
        result = generate_vacancy_with_ai(
            title=title,
            employment_type=employment_type,
            description_tasks=description_tasks,
            description_conditions=description_conditions
        )
        
        current_app.logger.info(f"Получен ответ от OpenAI API: {json.dumps(result, ensure_ascii=False)}")
        
        # Проверяем структуру данных
        if 'questions' in result:
            current_app.logger.info(f"Вопросы в ответе: {json.dumps(result['questions'], ensure_ascii=False)}")
        if 'soft_questions' in result:
            current_app.logger.info(f"Soft вопросы в ответе: {json.dumps(result['soft_questions'], ensure_ascii=False)}")
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except Exception as e:
        current_app.logger.error(f'Ошибка при генерации вакансии: {str(e)}')
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@vacancies_bp.route('/update_selection_stages/<int:id>', methods=['POST'])
@login_required
def update_selection_stages(id):
    """Обновление этапов отбора для вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Проверка прав доступа
    if vacancy.created_by != current_user.id and current_user.role != 'admin':
        flash('У вас нет прав на редактирование этой вакансии', 'danger')
        return redirect(url_for('vacancies.list'))
    
    try:
        # Получаем данные о этапах из формы
        stages_data = request.form.get('selection_stages_json', '[]')
        stages_list = json.loads(stages_data)
        
        # Проверяем данные и добавляем при необходимости
        if isinstance(stages_list, list):
            # Проверяем, что каждый этап имеет необходимые поля
            validated_stages = []
            for stage in stages_list:
                if isinstance(stage, dict) and 'name' in stage:
                    # Если нет описания, добавляем его
                    if 'description' not in stage:
                        stage['description'] = f"Этап отбора: {stage['name']}"
                    validated_stages.append(stage)
            
            # Обновляем этапы отбора в вакансии
            vacancy.selection_stages_json = validated_stages
            db.session.commit()
            
            # Логируем обновление
            SystemLog.log(
                event_type="vacancy_selection_stages_update",
                description=f"Обновлены этапы отбора для вакансии ID={id}",
                user_id=current_user.id,
                ip_address=request.remote_addr
            )
            
            flash('Этапы отбора успешно обновлены', 'success')
        else:
            flash('Некорректный формат данных для этапов отбора', 'danger')
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Ошибка при обновлении этапов отбора: {str(e)}")
        flash(f'Ошибка при обновлении этапов отбора: {str(e)}', 'danger')
    
    return redirect(url_for('vacancies.edit', id=id))

@vacancies_bp.route('/get_default_stages')
@login_required
def get_default_stages():
    """Получение стандартных этапов отбора"""
    # Стандартные этапы отбора
    default_stages = [
        {"name": "Рассмотрение резюме", "description": "Резюме кандидата на рассмотрении"},
        {"name": "Тестовое задание", "description": "Кандидат выполняет тестовое задание"},
        {"name": "Собеседование с HR", "description": "Запланировано собеседование с HR-менеджером"},
        {"name": "Техническое интервью", "description": "Запланировано техническое собеседование"},
        {"name": "Предложение", "description": "Кандидату сделано предложение"}
    ]
    
    return jsonify(default_stages)

@vacancies_bp.route('/<int:id>/delete', methods=['POST'])
@profile_time
@login_required
def delete(id):
    """Удаление вакансии"""
    vacancy = Vacancy.query.get_or_404(id)
    
    # Проверяем, принадлежит ли вакансия текущему пользователю
    if vacancy.created_by != current_user.id:
        flash('У вас нет доступа к удалению этой вакансии', 'danger')
        return redirect(url_for('vacancies.index'))
    
    try:
        # Проверяем, есть ли связанные кандидаты
        candidates_count = Candidate.query.filter_by(vacancy_id=vacancy.id).count()
        if candidates_count > 0:
            flash('Невозможно удалить вакансию, так как есть связанные кандидаты', 'danger')
            return redirect(url_for('vacancies.index'))
        
        # Удаляем вакансию
        db.session.delete(vacancy)
        db.session.commit()
        
        # Логирование
        SystemLog.log(
                event_type="delete_vacancy",
                description=f"Удалена вакансия: {vacancy.title}",
            user_id=current_user.id,
            ip_address=request.remote_addr
        )
    
        flash('Вакансия успешно удалена', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Ошибка при удалении вакансии: {str(e)}")
        flash('Произошла ошибка при удалении вакансии', 'danger')
    
    return redirect(url_for('vacancies.index')) 