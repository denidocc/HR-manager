#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import os
from flask import current_app
import re
import random

def request_ai_analysis(resume_text, vacancy_description):
    """
    Отправляет текст резюме и описание вакансии на анализ с использованием AI
    и возвращает результаты анализа.
    
    В реальном приложении здесь был бы код для работы с API нейросети,
    но для демонстрационных целей мы используем заглушку.
    
    Args:
        resume_text (str): Текст резюме кандидата
        vacancy_description (str): Описание вакансии
        
    Returns:
        dict: Результаты анализа, включая процент соответствия и ключевые навыки
    """
    # В реальном приложении здесь был бы запрос к AI-сервису
    try:
        # Эмуляция обработки и анализа
        # В реальном приложении здесь был бы код для отправки запроса к API нейросети
        
        # Извлекаем ключевые слова для эмуляции анализа
        skills_pattern = r'(Python|Java|JavaScript|SQL|HTML|CSS|React|Angular|Vue|Flask|Django|Spring|AI|ML)'
        resume_skills = set(re.findall(skills_pattern, resume_text, re.IGNORECASE))
        vacancy_skills = set(re.findall(skills_pattern, vacancy_description, re.IGNORECASE))
        
        # Находим совпадающие навыки
        matching_skills = resume_skills.intersection(vacancy_skills)
        
        # Эмулируем процент соответствия
        if len(vacancy_skills) == 0:
            match_percent = random.randint(50, 90)
        else:
            match_percent = int(len(matching_skills) / len(vacancy_skills) * 100)
            # Добавляем немного случайности
            match_percent = min(100, match_percent + random.randint(-10, 10))
        
        # Формируем результаты анализа
        analysis_results = {
            'match_percent': match_percent,
            'matching_skills': list(matching_skills),
            'missing_skills': list(vacancy_skills - resume_skills),
            'additional_skills': list(resume_skills - vacancy_skills),
            'summary': generate_ai_summary(resume_text, vacancy_description, match_percent)
        }
        
        current_app.logger.info(f"AI анализ выполнен успешно, соответствие: {match_percent}%")
        return analysis_results
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при выполнении AI анализа: {str(e)}")
        return {
            'match_percent': 0,
            'matching_skills': [],
            'missing_skills': [],
            'additional_skills': [],
            'summary': "Не удалось выполнить анализ",
            'error': str(e)
        }

def generate_ai_summary(resume_text, vacancy_description, match_percent):
    """
    Генерирует краткое резюме анализа на основе текста резюме и описания вакансии.
    
    Args:
        resume_text (str): Текст резюме кандидата
        vacancy_description (str): Описание вакансии
        match_percent (int): Процент соответствия
        
    Returns:
        str: Текстовое резюме анализа
    """
    # Заглушки для различных уровней соответствия
    if match_percent >= 90:
        return "Кандидат отлично подходит для данной позиции. Имеет все требуемые навыки и опыт работы."
    elif match_percent >= 70:
        return "Кандидат хорошо подходит для данной позиции. Обладает большинством требуемых навыков."
    elif match_percent >= 50:
        return "Кандидат может подойти для данной позиции, но не обладает некоторыми ключевыми навыками."
    else:
        return "Кандидат не соответствует требованиям позиции. Рекомендуется рассмотреть других кандидатов."

def get_analysis_status(analysis_id):
    """
    Проверяет статус анализа по его идентификатору.
    
    В реальном приложении здесь был бы запрос к API для проверки статуса задачи анализа.
    Для демонстрационных целей мы всегда возвращаем завершенный статус.
    
    Args:
        analysis_id (str): Идентификатор задачи анализа
        
    Returns:
        dict: Информация о статусе анализа
    """
    # Эмуляция проверки статуса
    try:
        # В реальном приложении здесь был бы запрос к API
        
        # Для демонстрации всегда возвращаем, что анализ завершен
        status_info = {
            'status': 'completed',
            'progress': 100,
            'analysis_id': analysis_id,
            'started_at': '2023-01-01T12:00:00',
            'completed_at': '2023-01-01T12:05:00'
        }
        
        return status_info
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при проверке статуса анализа: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'analysis_id': analysis_id
        } 