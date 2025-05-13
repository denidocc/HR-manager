#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import os
from flask import current_app
import re
import random
from openai import OpenAI
import uuid
import time
from dotenv import load_dotenv  # Добавляем импорт для перезагрузки переменных окружения

def test_openai_api_key():
    """
    Тестирует текущий API-ключ OpenAI, чтобы проверить его работоспособность.
    
    Returns:
        bool: True если ключ работает, False в противном случае
        str: Сообщение о статусе или ошибке
    """
    try:
        # Принудительно перезагружаем переменные окружения
        load_dotenv(override=True)
        
        # Получаем API ключ из конфигурации
        api_key = current_app.config.get('OPENAI_API_KEY')
        
        # Если ключ не найден в конфигурации, пробуем получить его из переменных окружения
        if not api_key or "your-" in api_key or len(api_key.strip()) < 20:
            api_key = os.environ.get('OPENAI_API_KEY')
            
        # Проверяем валидность ключа
        if not api_key or "your-" in api_key or len(api_key.strip()) < 20:
            return False, f"Некорректный API-ключ: {api_key[:10]}... (длина: {len(api_key) if api_key else 0})"
        
        # Создаем клиента OpenAI с этим ключом
        client = OpenAI(api_key=api_key)
        
        # Выполняем простой запрос для проверки ключа
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - помощник."},
                {"role": "user", "content": "Скажи 'Ключ работает!' одной строкой"}
            ],
            max_tokens=10
        )
        
        # Получаем ответ
        result = response.choices[0].message.content.strip()
        
        return True, f"API-ключ работает. Ответ: {result}"
        
    except Exception as e:
        return False, f"Ошибка при проверке API-ключа: {str(e)}"

def request_ai_analysis(candidate):
    """
    Отправляет данные кандидата на анализ с использованием OpenAI API
    и возвращает результаты анализа.
    
    Args:
        candidate: Объект кандидата с данными для анализа
        
    Returns:
        dict: Результаты анализа, включая процент соответствия и рекомендации
    """
    try:
        # Принудительно перезагружаем переменные окружения
        load_dotenv(override=True)
        
        # Получаем API ключ напрямую из переменных окружения
        api_key_env = os.environ.get('OPENAI_API_KEY')
        
        # Маскируем ключ для логов
        masked_key = f"{api_key_env[:5]}...{'*' * 5}" if api_key_env else "None"
        current_app.logger.info(f"OPENAI_API_KEY напрямую из os.environ: {masked_key} (длина: {len(api_key_env) if api_key_env else 0})")
        
        # Проверяем, что ключ из переменной окружения валидный
        if api_key_env and "your-" not in api_key_env and len(api_key_env.strip()) >= 20:
            api_key = api_key_env
        else:
            # Если ключ из окружения невалидный, пробуем получить из конфигурации
            api_key = current_app.config.get('OPENAI_API_KEY')
            masked_key = f"{api_key[:5]}...{'*' * 5}" if api_key else "None"
            current_app.logger.info(f"OPENAI_API_KEY из конфигурации: {masked_key} (длина: {len(api_key) if api_key else 0})")
        
        # Проверяем валидность ключа
        if not api_key or "your-" in api_key or len(api_key.strip()) < 20:
            current_app.logger.error("OpenAI API ключ невалидный или отсутствует")
            return None
        
        # Проверяем работоспособность ключа
        key_valid, message = test_openai_api_key()
        if not key_valid:
            current_app.logger.error(f"Проверка API-ключа не прошла: {message}")
            return None
            
        current_app.logger.info(f"API-ключ OpenAI прошел проверку: {message}")
            
        # Инициализация клиента OpenAI
        client = OpenAI(api_key=api_key)
        
        # Получаем данные вакансии
        vacancy = candidate.vacancy
        
        # Подготовка данных кандидата
        # Получаем базовую информацию
        location = candidate.base_answers.get('location', 'Не указано') if candidate.base_answers else 'Не указано'
        experience_years = candidate.base_answers.get('experience_years', 'Не указано') if candidate.base_answers else 'Не указано'
        education = candidate.base_answers.get('education', 'Не указано') if candidate.base_answers else 'Не указано'
        
        # Преобразуем образование из кода в текстовое описание
        education_translations = {
            'secondary': 'Среднее',
            'vocational': 'Среднее специальное',
            'higher': 'Высшее',
            'phd': 'Ученая степень'
        }
        education_text = education_translations.get(education, education)
        
        # Формируем информацию о местоположении для AI
        location_info = location
        if location and location != 'Не указано':
            # Добавляем дополнительную информацию для AI о местоположении
            location_info = f"{location} (указан город проживания кандидата)"
        
        # Подготовка ответов на профессиональные вопросы
        professional_answers = ""
        if candidate.vacancy_answers and vacancy.questions_json:
            question_texts = {str(q['id']): q['text'] for q in vacancy.questions_json}
            for question_id, answer in candidate.vacancy_answers.items():
                question_text = question_texts.get(question_id, f"Вопрос {question_id}")
                professional_answers += f"Вопрос: {question_text}\nОтвет: {answer}\n\n"
        
        # Подготовка ответов на вопросы о soft skills
        soft_skills_answers = ""
        if candidate.soft_answers and vacancy.soft_questions_json:
            soft_question_texts = {str(q['id']): q['text'] for q in vacancy.soft_questions_json}
            for question_id, answer in candidate.soft_answers.items():
                question_text = soft_question_texts.get(question_id, f"Вопрос {question_id}")
                soft_skills_answers += f"Вопрос: {question_text}\nОтвет: {answer}\n\n"
        
        prompt = f"""
        Проанализируй соответствие кандидата требованиям вакансии и оцени по 100-балльной шкале.

        ВАКАНСИЯ:
        Название: {vacancy.title}
        Тип занятости: {vacancy.c_employment_type.name if vacancy.c_employment_type else 'Не указано'}
        Описание задач: {vacancy.description_tasks or 'Не указано'}
        Условия работы: {vacancy.description_conditions or 'Не указано'}
        Требования к кандидату: {vacancy.ideal_profile or 'Не указано'}
        Корпоративные ценности: {vacancy.company_values or 'Не указано'}

        КАНДИДАТ:
        ФИО: {candidate.full_name}
        Город: {location_info}
        Опыт работы: {experience_years}
        Образование: {education_text}
        Зарплатные ожидания: {candidate.base_answers.get('desired_salary', 'Не указано') if candidate.base_answers else 'Не указано'}
        {f"Кандидат ранее подавался на позиции: {candidate.previous_applications}" if hasattr(candidate, 'previous_applications') and candidate.previous_applications else ""}

        Профессиональные вопросы и ответы (Очень важно учитывать эти ответы при оценке):
        {professional_answers}

        Вопросы о soft skills и ответы (Очень важно учитывать эти ответы при оценке):
        {soft_skills_answers}

        РЕЗЮМЕ КАНДИДАТА:
        {candidate.resume_text[:10000] if candidate.resume_text else 'Не предоставлено'}

        {f"СОПРОВОДИТЕЛЬНОЕ ПИСЬМО:\n{candidate.cover_letter[:3000]}" if candidate.cover_letter else ""}

        ПРОВЕРКА ПОЛНОТЫ ДАННЫХ:
        В первую очередь определи, достаточно ли информации для адекватной оценки кандидата. Обязательными полями считаются:
        - Базовая информация о кандидате (ФИО, опыт работы)
        - Либо резюме, либо ответы на профессиональные вопросы

        Если данных недостаточно, укажи это в результате анализа и предложи, какую дополнительную информацию необходимо запросить.

        ОЦЕНКА КАЧЕСТВА ИНФОРМАЦИИ:
        Проанализируй детализацию и качество предоставленных данных:
        - Оцени полноту и детализацию резюме
        - Проверь качество ответов на вопросы (развернутые vs поверхностные)
        - Оцени наличие признаков генерации контента с помощью ИИ

        Оцени соответствие кандидата требованиям вакансии по следующим критериям:
        1. Местоположение (от 0 до 100)
        2. Опыт работы (от 0 до 100)
        3. Технические навыки (от 0 до 100)
        4. Образование (от 0 до 100)
        5. Soft skills (от 0 до 100)
        6. Мотивация и соответствие ценностям компании (от 0 до 100)
        7. Стабильность трудовой истории (от 0 до 100)
        8. Актуальность профессионального опыта (от 0 до 100)

        Для каждого критерия напиши короткий комментарий, объясняющий оценку.

        ВАЖНО: Географическое соответствие (местоположение) считай нейтральным фактором, НЕ включай его в список сильных сторон кандидата. Это базовое условие, а не преимущество.

        ВЫЯВЛЕНИЕ НЕСООТВЕТСТВИЙ:
        Внимательно сравни информацию в резюме кандидата с ответами на вопросы и данными из формы. Укажи любые противоречия или несоответствия, которые могут вызвать сомнения в достоверности предоставленных данных.

        АНАЛИЗ КАРЬЕРНОЙ ДИНАМИКИ:
        Оцени скорость карьерного роста кандидата, проанализируй продвижение по должностям и расширение обязанностей.
        Рассчитай среднюю продолжительность работы на одном месте и сделай прогноз вероятности долгосрочной работы в компании.
        Если есть перерывы в карьере, проанализируй их причины и влияние на квалификацию.

        ДЕТАЛИЗАЦИЯ ТЕХНИЧЕСКИХ НАВЫКОВ:
        Разбей имеющиеся навыки кандидата на три категории:
        - Ключевые навыки (критически важные для позиции)
        - Дополнительные навыки (полезные, но не критичные)
        - Отсутствующие навыки (требуемые, но не представленные у кандидата)

        ОЦЕНКА ПРОЕКТНОГО ОПЫТА:
        Определи масштаб проектов, в которых участвовал кандидат, и сопоставь с требованиями вакантной позиции.
        Оцени конкретные достижения и их релевантность.

        АНАЛИЗ ОСОБЫХ СЛУЧАЕВ:
        Проверь наличие следующих особых обстоятельств:
        - Смена сферы деятельности (career switch)
        - Комбинация разных форм занятости
        - Перерывы в карьере и их продолжительность
        - Неоднократные смены работы за короткий период
        - Необходимость визовой/миграционной поддержки
        - Повторная заявка (если кандидат уже ранее подавался)

        Составь:
        - Список сильных сторон кандидата (не более 5 пунктов)
        - Список нейтральных факторов (таких как местоположение)
        - Список слабых сторон или несоответствий требованиям (не более 5 пунктов)
        - Общую рекомендацию: пригласить на собеседование, отклонить или запросить дополнительную информацию
        - Если есть несоответствия требованиям, укажи их конкретно
        - Список из 3-5 вопросов для уточнения на собеседовании
        - Оценку срочности реакции на кандидата (от 1 до 5, где 5 - очень срочно)
        - Прогноз долгосрочной мотивации и потенциала роста в компании

        Проверь наличие критических стоп-факторов:
        - Несоответствие обязательным требованиям (указать какие)
        - Несоответствие локации, если удаленная работа невозможна
        - Несоответствие ожиданий по зарплате возможностям компании
        - Признаки "keyword stuffing" (искусственное добавление ключевых слов)
        - Потенциальные конфликты интересов
        - Иные критические факторы, делающие найм невозможным

        Проанализируй скрытый потенциал:
        - Выяви неочевидные навыки, которые могут быть полезны для позиции
        - Оцени способность к адаптации в новой среде на основе опыта работы в разных компаниях
        - Определи коммуникативные навыки на основе качества резюме и сопроводительного письма

        Верни результат в формате JSON:
        {{
            "data_completeness": {{
                "sufficient_for_analysis": true/false,
                "missing_information": ["поле 1", "поле 2", ...] или [],
                "data_quality_assessment": "оценка качества данных",
                "ai_generated_content_signs": true/false
            }},
            "match_percent": число от 0 до 100,
            "confidence_score": число от 0 до 100, // насколько уверен в оценке на основе полноты данных
            "pros": ["сильная сторона 1", "сильная сторона 2", ...],
            "neutral_factors": ["нейтральный фактор 1", "нейтральный фактор 2", ...],
            "cons": ["слабая сторона 1", "слабая сторона 2", ...],
            "recommendation": "текст рекомендации",
            "scores": {{
                "location": число от 0 до 100,
                "experience": число от 0 до 100,
                "tech_skills": число от 0 до 100,
                "education": число от 0 до 100,
                "soft_skills": число от 0 до 100,
                "motivation_and_values": число от 0 до 100,
                "employment_stability": число от 0 до 100,
                "experience_relevance": число от 0 до 100
            }},
            "score_comments": {{
                "location": "комментарий",
                "experience": "комментарий",
                "tech_skills": "комментарий",
                "education": "комментарий",
                "soft_skills": "комментарий",
                "motivation_and_values": "комментарий",
                "employment_stability": "комментарий",
                "experience_relevance": "комментарий"
            }},
            "skills_breakdown": {{
                "key_skills": ["навык 1", "навык 2", ...],
                "additional_skills": ["навык 1", "навык 2", ...],
                "missing_skills": ["навык 1", "навык 2", ...]
            }},
            "career_dynamics": {{
                "growth_rate": "описание скорости роста",
                "avg_tenure": "средняя продолжительность на одном месте в годах",
                "stability_assessment": "оценка стабильности",
                "career_gaps": ["период 1: причина", "период 2: причина", ...] или []
            }},
            "special_cases": {{
                "career_switch": true/false,
                "mixed_employment": true/false,
                "frequent_job_changes": true/false,
                "visa_support_required": true/false,
                "repeated_application": true/false,
                "details": "описание особых обстоятельств, если есть"
            }},
            "inconsistencies": ["несоответствие 1", "несоответствие 2", ...] или [],
            "mismatch_notes": "текст о несоответствиях требованиям, если есть",
            "interview_questions": ["вопрос 1", "вопрос 2", ...],
            "urgency_rating": число от 1 до 5,
            "stop_factors": ["стоп-фактор 1", "стоп-фактор 2", ...] или [],
            "hidden_potential": {{
                "non_obvious_skills": ["навык 1", "навык 2", ...],
                "adaptability_assessment": "оценка адаптивности",
                "communication_skills": "оценка коммуникативных навыков"
            }},
            "long_term_outlook": {{
                "motivation_sustainability": "прогноз долгосрочной мотивации",
                "growth_potential": "потенциал роста в компании"
            }},
            "additional_information_required": ["информация 1", "информация 2", ...] или [],
            "legal_ethical_concerns": ["проблема 1", "проблема 2", ...] или []
        }}
        """   
        
        # Отправляем запрос к OpenAI API
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты - HR-аналитик, специализирующийся на оценке соответствия кандидатов требованиям вакансий."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        # Получаем ответ
        result_text = response.choices[0].message.content.strip()
        
        # Парсим JSON
        result = json.loads(result_text)
        
        # Обновляем данные кандидата
        candidate.ai_match_percent = result.get('match_percent')
        candidate.ai_pros = result.get('pros')
        candidate.ai_cons = result.get('cons')
        candidate.ai_recommendation = result.get('recommendation')
        
        # Обновляем оценки по категориям
        scores = result.get('scores', {})
        candidate.ai_score_location = scores.get('location')
        candidate.ai_score_experience = scores.get('experience')
        candidate.ai_score_tech = scores.get('tech_skills')
        candidate.ai_score_education = scores.get('education')
        
        # Обновляем комментарии к оценкам
        score_comments = result.get('score_comments', {})
        candidate.ai_score_comments_location = score_comments.get('location')
        candidate.ai_score_comments_experience = score_comments.get('experience')
        candidate.ai_score_comments_tech = score_comments.get('tech_skills')
        candidate.ai_score_comments_education = score_comments.get('education')
        
        # Обновляем заметки о несоответствиях
        candidate.ai_mismatch_notes = result.get('mismatch_notes')
        
        # Сохраняем изменения в БД
        from app import db
        db.session.commit()
        
        # Генерируем уникальный ID для задачи
        job_id = str(uuid.uuid4())
        
        return job_id
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при запросе AI-анализа: {str(e)}")
        return None

def get_analysis_status(analysis_id):
    """
    Проверяет статус анализа по его идентификатору.
    
    В текущей реализации анализ выполняется синхронно,
    поэтому всегда возвращаем завершенный статус.
    
    Args:
        analysis_id (str): Идентификатор задачи анализа
        
    Returns:
        dict: Информация о статусе анализа
    """
    try:
        # Для текущей реализации всегда возвращаем, что анализ завершен
        status_info = {
            'status': 'completed',
            'progress': 100,
            'analysis_id': analysis_id,
            'started_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'completed_at': time.strftime('%Y-%m-%dT%H:%M:%S')
        }
        
        return status_info
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при проверке статуса анализа: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'analysis_id': analysis_id
        }

def analyze_vacancy_requirements(vacancy_description):
    """
    Анализирует требования вакансии с помощью OpenAI API
    для извлечения ключевых навыков и требований.
    
    Args:
        vacancy_description (str): Описание вакансии
        
    Returns:
        dict: Извлеченные требования и навыки
    """
    try:
        # Принудительно перезагружаем переменные окружения
        load_dotenv(override=True)
        
        # Получаем API ключ напрямую из переменных окружения
        api_key_env = os.environ.get('OPENAI_API_KEY')
        
        # Маскируем ключ для логов
        masked_key = f"{api_key_env[:5]}...{'*' * 5}" if api_key_env else "None"
        current_app.logger.info(f"OPENAI_API_KEY напрямую из os.environ: {masked_key} (длина: {len(api_key_env) if api_key_env else 0})")
        
        # Проверяем, что ключ из переменной окружения валидный
        if api_key_env and "your-" not in api_key_env and len(api_key_env.strip()) >= 20:
            api_key = api_key_env
        else:
            # Если ключ из окружения невалидный, пробуем получить из конфигурации
            api_key = current_app.config.get('OPENAI_API_KEY')
            masked_key = f"{api_key[:5]}...{'*' * 5}" if api_key else "None"
            current_app.logger.info(f"OPENAI_API_KEY из конфигурации: {masked_key} (длина: {len(api_key) if api_key else 0})")
        
        # Проверяем валидность ключа
        if not api_key or "your-" in api_key or len(api_key.strip()) < 20:
            current_app.logger.error("OpenAI API ключ невалидный или отсутствует")
            return None
        
        # Формируем запрос для анализа
        prompt = f"""
        Проанализируй описание вакансии и извлеки ключевые требования и навыки:
        
        {vacancy_description}
        
        Верни результат в формате JSON:
        {{
            "required_skills": ["навык1", "навык2", ...],
            "required_experience": "описание требуемого опыта",
            "required_education": "требования к образованию",
            "job_responsibilities": ["обязанность1", "обязанность2", ...],
            "keywords": ["ключевое слово1", "ключевое слово2", ...]
        }}
        """
        
        # Отправляем запрос к OpenAI API
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - HR-аналитик, специализирующийся на анализе вакансий."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        # Получаем ответ
        result_text = response.choices[0].message.content.strip()
        
        # Парсим JSON
        result = json.loads(result_text)
        
        return result
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при анализе требований вакансии: {str(e)}")
        return None 