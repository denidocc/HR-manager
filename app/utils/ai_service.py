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
        # Получаем API ключ из конфигурации
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            current_app.logger.error("OpenAI API ключ не найден в конфигурации")
            return None
            
        # Инициализация клиента OpenAI
        client = OpenAI(api_key=api_key)
        
        # Получаем данные вакансии
        vacancy = candidate.vacancy
        
        # Формируем запрос для анализа
        prompt = f"""
        Проанализируй соответствие кандидата требованиям вакансии и оцени по 100-балльной шкале.
        
        ВАКАНСИЯ:
        Название: {vacancy.title}
        Тип занятости: {vacancy.employment_type}
        Описание задач: {vacancy.job_description}
        Условия работы: {vacancy.conditions}
        Требования к кандидату: {vacancy.requirements}
        
        КАНДИДАТ:
        ФИО: {candidate.full_name}
        Город: {candidate.location}
        Опыт работы: {candidate.experience_years} лет
        Образование: {candidate.education}
        
        Ответы на профессиональные вопросы:
        {candidate.professional_answers}
        
        Ответы на вопросы о личных качествах:
        {candidate.soft_skills_answers}
        
        Сопроводительное письмо:
        {candidate.cover_letter}
        
        Текст резюме:
        {candidate.resume_text}
        
        Проведи детальный анализ и предоставь следующую информацию:
        1. Общий процент соответствия кандидата вакансии (от 0 до 100)
        2. Сильные стороны кандидата (список из 3-5 пунктов)
        3. Слабые стороны или области для развития (список из 3-5 пунктов)
        4. Рекомендация по кандидату (принять/отклонить/рассмотреть)
        5. Оценки по категориям (от 1 до 10):
           - Локация (насколько местоположение кандидата соответствует требованиям)
           - Опыт работы (релевантность и достаточность)
           - Технические навыки (соответствие требуемым навыкам)
           - Образование (релевантность и уровень)
        6. Комментарии по каждой категории
        7. Примечания о несоответствии (если есть)
        
        Формат ответа должен быть строго в JSON:
        {
            "match_percent": число,
            "pros": ["пункт1", "пункт2", ...],
            "cons": ["пункт1", "пункт2", ...],
            "recommendation": "текст рекомендации",
            "scores": {
                "location": число,
                "experience": число,
                "tech": число,
                "education": число
            },
            "comments": {
                "location": "текст",
                "experience": "текст",
                "tech": "текст",
                "education": "текст"
            },
            "mismatch_notes": "текст о несоответствиях"
        }
        """
        
        # Отправляем запрос к OpenAI API
        current_app.logger.info(f"Отправка запроса к OpenAI API для анализа кандидата ID={candidate.id}")
        
        response = client.chat.completions.create(
            model="gpt-4o",  # Используем мощную модель для анализа
            messages=[
                {"role": "system", "content": "Ты - HR-аналитик, специализирующийся на оценке соответствия кандидатов требованиям вакансий."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Получаем и парсим ответ
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        
        # Сохраняем результаты анализа в базу данных
        candidate.ai_match_percent = result["match_percent"]
        candidate.ai_pros = "\n".join(result["pros"])
        candidate.ai_cons = "\n".join(result["cons"])
        candidate.ai_recommendation = result["recommendation"]
        
        # Сохраняем оценки по категориям
        candidate.ai_score_location = result["scores"]["location"]
        candidate.ai_score_experience = result["scores"]["experience"]
        candidate.ai_score_tech = result["scores"]["tech"]
        candidate.ai_score_education = result["scores"]["education"]
        
        # Сохраняем комментарии
        candidate.ai_score_comments_location = result["comments"]["location"]
        candidate.ai_score_comments_experience = result["comments"]["experience"]
        candidate.ai_score_comments_tech = result["comments"]["tech"]
        candidate.ai_score_comments_education = result["comments"]["education"]
        
        # Сохраняем примечания о несоответствии
        candidate.ai_mismatch_notes = result["mismatch_notes"]
        
        # Сохраняем изменения в базе данных
        from app import db
        db.session.commit()
        
        current_app.logger.info(f"AI анализ выполнен успешно, соответствие: {candidate.ai_match_percent}%")
        
        # Генерируем уникальный ID для задачи анализа
        job_id = str(uuid.uuid4())
        return job_id
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при выполнении AI анализа: {str(e)}")
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
        # Получаем API ключ из конфигурации
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            current_app.logger.error("OpenAI API ключ не найден в конфигурации")
            return None
            
        # Инициализация клиента OpenAI
        client = OpenAI(api_key=api_key)
        
        prompt = f"""
        Проанализируй описание вакансии и извлеки из него ключевые требования и навыки.
        
        ОПИСАНИЕ ВАКАНСИИ:
        {vacancy_description}
        
        Предоставь результат в следующем формате JSON:
        {{
            "required_skills": ["навык1", "навык2", ...],
            "preferred_skills": ["навык1", "навык2", ...],
            "experience_years": число,
            "education_level": "уровень образования",
            "key_responsibilities": ["обязанность1", "обязанность2", ...],
            "location_requirements": "требования к локации"
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты - HR-аналитик, специализирующийся на анализе вакансий."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        
        return result
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при анализе требований вакансии: {str(e)}")
        return None 