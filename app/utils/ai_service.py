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
import base64
import docx
import fitz
from PIL import Image
import io
from datetime import datetime, timezone, timedelta
from threading import Thread
import logging

# Настройка логгера для использования вне контекста приложения
logger = logging.getLogger('resume_processor')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

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
            model="gpt-4o",
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

def extract_resume_text(file_path):
    """
    Извлекает текст из файла резюме с использованием OpenAI API или других методов,
    в зависимости от формата файла.
    
    Args:
        file_path (str): Путь к файлу резюме
        
    Returns:
        dict: Словарь с извлеченным текстом и структурированными данными
    """
    current_app.logger.info(f"Начало извлечения текста из файла: {file_path}")
    
    if not file_path or not os.path.exists(file_path):
        current_app.logger.error(f"Файл не существует или путь не указан: {file_path}")
        return None
    
    try:
        # Определяем формат файла по расширению
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Получаем API ключ
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key or "your-" in api_key or len(api_key.strip()) < 20:
            api_key = os.environ.get('OPENAI_API_KEY')
        
        # Проверяем валидность ключа
        if not api_key or "your-" in api_key or len(api_key.strip()) < 20:
            current_app.logger.error("OpenAI API ключ невалидный или отсутствует")
            return None
        
        # Создаем клиента OpenAI
        client = OpenAI(api_key=api_key)
        
        # Обработка в зависимости от формата файла
        if file_extension in ['.pdf']:
            # Для PDF используем PyMuPDF для преобразования в изображения
            current_app.logger.info(f"Обрабатываем PDF-файл через конвертацию в изображения: {file_path}")
            
            # Открываем PDF с помощью PyMuPDF
            pdf_document = fitz.open(file_path)
            
            # Подготовка списка для хранения текста со всех страниц
            all_pages_text = []
            
            # Для каждой страницы PDF
            for page_num in range(len(pdf_document)):
                # Получаем страницу
                page = pdf_document[page_num]
                
                # Преобразуем страницу в изображение
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Увеличиваем разрешение для лучшего распознавания
                
                # Конвертируем pixmap в формат, который можно отправить в OpenAI API
                img_data = pix.tobytes("png")
                
                # Кодируем изображение в base64
                img_base64 = base64.b64encode(img_data).decode('utf-8')
                
                # Отправляем запрос к OpenAI API для извлечения текста из изображения
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "Ты специалист по распознаванию текста из документов. Извлеки весь текст из предоставленного изображения страницы резюме, сохраняя структуру и форматирование. Важно: удали все технические артефакты, такие как URL-адреса с номерами страниц, IP-адреса, пути к файлам, технические заголовки и метаданные. Не включай в результат строки, содержащие 'mypanel', 'mpanel', 'details.php', 'print=1' и подобные технические элементы. При этом СОХРАНЯЙ профессиональные ссылки на GitHub, GitLab, LinkedIn, личные сайты и портфолио кандидата - они важны для оценки."
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Это страница {page_num + 1} из {len(pdf_document)} резюме. Извлеки весь текст с этой страницы, но удали все технические артефакты, такие как URL-адреса с номерами страниц, IP-адреса, пути к файлам. Сохрани профессиональные ссылки (GitHub, LinkedIn, портфолио и т.д.) - они важны для оценки кандидата."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=4096
                )
                
                # Извлекаем распознанный текст из ответа
                page_text = response.choices[0].message.content
                all_pages_text.append(page_text)
            
            # Закрываем документ
            pdf_document.close()
            
            # Объединяем текст со всех страниц
            raw_text = "\n\n".join(all_pages_text)
            
        elif file_extension in ['.docx']:
            # Для DOCX используем python-docx для извлечения текста
            try:
                doc = docx.Document(file_path)
                paragraphs = [p.text for p in doc.paragraphs]
                raw_text = "\n".join(paragraphs)
                
                # Если текст слишком короткий или неполный, используем OpenAI как запасной вариант
                if len(raw_text) < 100:
                    current_app.logger.warning(f"Извлечено мало текста из DOCX, пробуем через OpenAI: {file_path}")
                    
                    # Читаем файл как бинарные данные
                    with open(file_path, "rb") as file:
                        file_data = file.read()
                    
                    # Пробуем отправить напрямую как бинарные данные
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {
                                    "role": "system",
                                    "content": "Ты специалист по распознаванию текста из резюме. Извлеки весь текст из предоставленного документа. Важно: удали все технические артефакты, такие как URL-адреса с номерами страниц, IP-адреса, пути к файлам, технические заголовки и метаданные. Не включай в результат строки, содержащие 'mypanel', 'mpanel', 'details.php', 'print=1' и подобные технические элементы. При этом СОХРАНЯЙ профессиональные ссылки на GitHub, GitLab, LinkedIn, личные сайты и портфолио кандидата - они важны для оценки."
                                },
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "Извлеки весь текст из этого резюме. Сохрани структуру и форматирование, но удали все технические артефакты, такие как URL-адреса с номерами страниц, IP-адреса, пути к файлам. Сохрани профессиональные ссылки (GitHub, LinkedIn, портфолио и т.д.) - они важны для оценки кандидата."
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:application/octet-stream;base64,{base64.b64encode(file_data).decode('utf-8')}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            max_tokens=4096
                        )
                        
                        raw_text = response.choices[0].message.content
                    except Exception as docx_api_error:
                        current_app.logger.warning(f"Не удалось обработать DOCX через API напрямую: {str(docx_api_error)}")
                        
                        # Если не удалось обработать напрямую, можно попробовать конвертировать DOCX в изображения
                        # Здесь можно использовать библиотеки для конвертации DOCX в PDF, а затем PDF в изображения
                        # Это более сложный процесс, который требует дополнительных библиотек
                        
                        # Пример использования текста, который мы уже извлекли
                        if len(raw_text) > 0:
                            current_app.logger.info(f"Используем текст, извлеченный с помощью python-docx: {len(raw_text)} символов")
                        else:
                            current_app.logger.error(f"Не удалось извлечь текст из DOCX-файла: {file_path}")
                            raw_text = "Не удалось извлечь текст из документа"
            except Exception as e:
                current_app.logger.error(f"Ошибка при извлечении текста из DOCX: {str(e)}")
                
                # Если не удалось извлечь текст через python-docx, используем OpenAI
                try:
                    with open(file_path, "rb") as file:
                        file_data = file.read()
                        
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "system",
                                "content": "Ты специалист по распознаванию текста из резюме. Извлеки весь текст из предоставленного документа. Важно: удали все технические артефакты, такие как URL-адреса с номерами страниц, IP-адреса, пути к файлам, технические заголовки и метаданные. Не включай в результат строки, содержащие 'mypanel', 'mpanel', 'details.php', 'print=1' и подобные технические элементы. При этом СОХРАНЯЙ профессиональные ссылки на GitHub, GitLab, LinkedIn, личные сайты и портфолио кандидата - они важны для оценки."
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Извлеки весь текст из этого резюме. Сохрани структуру и форматирование, но удали все технические артефакты, такие как URL-адреса с номерами страниц, IP-адреса, пути к файлам. Сохрани профессиональные ссылки (GitHub, LinkedIn, портфолио и т.д.) - они важны для оценки кандидата."
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:application/octet-stream;base64,{base64.b64encode(file_data).decode('utf-8')}"
                                        }
                                    }
                                ]
                            }
                        ],
                        max_tokens=4096
                    )
                    
                    raw_text = response.choices[0].message.content
                except Exception as api_error:
                    current_app.logger.error(f"Ошибка при обработке DOCX через API: {str(api_error)}")
                    raw_text = "Не удалось извлечь текст из документа"
                
        elif file_extension in ['.jpg', '.jpeg', '.png']:
            # Для изображений используем OpenAI Vision API
            try:
                with open(file_path, "rb") as file:
                    image_data = file.read()
                    
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "Ты специалист по распознаванию текста из резюме. Извлеки весь текст из предоставленного изображения, сохраняя структуру и форматирование. Важно: удали все технические артефакты, такие как URL-адреса с номерами страниц, IP-адреса, пути к файлам, технические заголовки и метаданные. Не включай в результат строки, содержащие 'mypanel', 'mpanel', 'details.php', 'print=1' и подобные технические элементы. При этом СОХРАНЯЙ профессиональные ссылки на GitHub, GitLab, LinkedIn, личные сайты и портфолио кандидата - они важны для оценки."
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Извлеки весь текст из этого резюме. Сохрани структуру и форматирование, но удали все технические артефакты, такие как URL-адреса с номерами страниц, IP-адреса, пути к файлам. Сохрани профессиональные ссылки (GitHub, LinkedIn, портфолио и т.д.) - они важны для оценки кандидата."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/{file_extension[1:]};base64,{base64.b64encode(image_data).decode('utf-8')}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=4096
                )
                
                raw_text = response.choices[0].message.content
            except Exception as e:
                current_app.logger.error(f"Ошибка при извлечении текста из изображения: {str(e)}")
                raw_text = "Не удалось извлечь текст из изображения"
        else:
            current_app.logger.error(f"Неподдерживаемый формат файла: {file_extension}")
            return None
        
        # Анализируем извлеченный текст для получения структурированных данных
        structured_data = extract_structured_data_from_text(raw_text, client)
        
        result = {
            "text": raw_text,
            "structured_data": structured_data
        }
        
        current_app.logger.info(f"Успешно извлечен текст из файла: {file_path}")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при извлечении текста из файла: {str(e)}", exc_info=True)
        return None

def extract_structured_data_from_text(text, client):
    """
    Извлекает структурированные данные из текста резюме с использованием OpenAI API
    
    Args:
        text (str): Текст резюме
        client (OpenAI): Клиент OpenAI API
        
    Returns:
        dict: Структурированные данные из резюме
    """
    try:
        # Создаем запрос к OpenAI для извлечения структурированных данных
        prompt = f"""
        Проанализируй следующий текст резюме и извлеки из него структурированные данные:
        
        {text[:6000]}  # Ограничиваем размер текста для API
        
        Верни результат в формате JSON со следующими полями:
        {{
            "personal_info": {{
                "name": "полное имя",
                "phone": "номер телефона",
                "email": "email адрес",
                "location": "город проживания"
            }},
            "education": [
                {{
                    "institution": "название учебного заведения",
                    "degree": "степень/квалификация",
                    "field": "специальность",
                    "year_start": "год начала",
                    "year_end": "год окончания"
                }}
            ],
            "experience": [
                {{
                    "company": "название компании",
                    "position": "должность",
                    "description": "описание обязанностей",
                    "year_start": "год начала",
                    "year_end": "год окончания или 'по настоящее время'"
                }}
            ],
            "skills": ["навык1", "навык2", ...],
            "languages": ["язык1", "язык2", ...],
            "summary": "краткое описание кандидата",
            "total_experience_years": "примерное количество лет опыта"
        }}
        
        Если какие-то данные отсутствуют, используй null или пустой массив.
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты - специалист по анализу резюме и извлечению структурированных данных."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        # Получаем ответ
        result_text = response.choices[0].message.content.strip()
        
        # Парсим JSON
        structured_data = json.loads(result_text)
        
        return structured_data
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при извлечении структурированных данных: {str(e)}", exc_info=True)
        return {}

def process_resume_and_analyze(candidate_id, resume_path):
    """
    Обрабатывает резюме кандидата и запускает AI-анализ
    
    Args:
        candidate_id (int): ID кандидата
        resume_path (str): Путь к файлу резюме
        
    Returns:
        bool: True если обработка успешна, False в противном случае
    """
    from app import db
    from app.models import Candidate
    
    # Создаем логгер для использования вне контекста приложения
    logger = logging.getLogger('resume_processor')
    
    try:
        # Получаем данные кандидата
        candidate = Candidate.query.get(candidate_id)
        if not candidate:
            logger.error(f"Кандидат с ID={candidate_id} не найден")
            return False
        
        logger.info(f"Начинаем обработку резюме для кандидата ID={candidate_id}, файл: {resume_path}")
        
        # Проверяем существование файла
        if not os.path.exists(resume_path):
            logger.error(f"Файл резюме не существует: {resume_path}")
            return False
        
        # Извлекаем текст из резюме
        resume_data = extract_resume_text(resume_path)
        if not resume_data:
            logger.error(f"Не удалось извлечь текст из резюме: {resume_path}")
            return False
        
        logger.info(f"Успешно извлечен текст из резюме, длина: {len(resume_data.get('text', ''))}")
        
        # Удаляем технические артефакты из текста
        cleaned_text = clean_resume_text(resume_data.get("text", ""))
        
        # Обновляем текст резюме в БД
        candidate.resume_text = cleaned_text
        
        # Если есть структурированные данные, сохраняем их
        if resume_data.get("structured_data"):
            logger.info(f"Получены структурированные данные из резюме")
            
            # Проверяем наличие базовых ответов
            if not candidate.base_answers:
                candidate.base_answers = {}
            
            # Обновляем базовые ответы из структурированных данных
            structured_data = resume_data["structured_data"]
            
            # Обновляем местоположение, если оно не было указано
            if structured_data.get("personal_info", {}).get("location") and (
                not candidate.base_answers.get("location") or 
                candidate.base_answers.get("location") == "Не указано"
            ):
                candidate.base_answers["location"] = structured_data["personal_info"]["location"]
                logger.info(f"Обновлено местоположение: {structured_data['personal_info']['location']}")
            
            # Обновляем опыт работы, если он не был указан
            if structured_data.get("total_experience_years") and (
                not candidate.base_answers.get("experience_years") or 
                candidate.base_answers.get("experience_years") == "Не указано"
            ):
                candidate.base_answers["experience_years"] = structured_data["total_experience_years"]
                logger.info(f"Обновлен опыт работы: {structured_data['total_experience_years']}")
            
            # Сохраняем структурированные данные в отдельное поле
            candidate.structured_resume_data = structured_data
        
        # Сохраняем изменения в БД
        db.session.commit()
        logger.info(f"Сохранены данные резюме в БД для кандидата ID={candidate_id}")
        
        # Запускаем AI-анализ
        job_id = request_ai_analysis(candidate)
        if not job_id:
            logger.error(f"Не удалось запустить AI-анализ для кандидата ID={candidate_id}")
            return False
        
        logger.info(f"Успешно обработано резюме и запущен AI-анализ (job_id={job_id}) для кандидата ID={candidate_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при обработке резюме и запуске анализа: {str(e)}", exc_info=True)
        try:
            db.session.rollback()
        except Exception as db_error:
            logger.error(f"Ошибка при откате транзакции: {str(db_error)}")
        return False

def clean_resume_text(text):
    """
    Очищает текст резюме от технических артефактов, но сохраняет полезные ссылки
    
    Args:
        text (str): Исходный текст резюме
        
    Returns:
        str: Очищенный текст
    """
    if not text:
        return ""
    
    import re
    
    # Сохраняем полезные ссылки на репозитории и профессиональные ресурсы
    # Создаем список для хранения найденных полезных ссылок
    useful_links = []
    
    # Находим ссылки на GitHub, GitLab, Bitbucket и другие репозитории
    github_links = re.findall(r'https?://(?:www\.)?github\.com/[\w\-\.]+(?:/[\w\-\.]+)*', text)
    gitlab_links = re.findall(r'https?://(?:www\.)?gitlab\.com/[\w\-\.]+(?:/[\w\-\.]+)*', text)
    bitbucket_links = re.findall(r'https?://(?:www\.)?bitbucket\.org/[\w\-\.]+(?:/[\w\-\.]+)*', text)
    
    # Добавляем найденные ссылки в список полезных ссылок
    useful_links.extend(github_links)
    useful_links.extend(gitlab_links)
    useful_links.extend(bitbucket_links)
    
    # Находим другие профессиональные ссылки (LinkedIn, портфолио и т.д.)
    linkedin_links = re.findall(r'https?://(?:www\.)?linkedin\.com/[\w\-\.]+(?:/[\w\-\.]+)*', text)
    portfolio_links = re.findall(r'https?://(?:www\.)?[\w\-\.]+\.(?:com|net|org|io|dev)/[\w\-\.]+(?:/[\w\-\.]+)*', text)
    
    # Добавляем найденные профессиональные ссылки
    useful_links.extend(linkedin_links)
    useful_links.extend(portfolio_links)
    
    # ПЕРВЫЙ ПРОХОД: Удаляем самые очевидные технические артефакты
    
    # Удаляем строки с IP-адресами и номерами страниц (СУПЕР агрессивно)
    text = re.sub(r'^.*\d+\.\d+\.\d+\.\d+.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^.*(?:\.php\?|\.asp\?|\.jsp\?|\.aspx\?).*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^.*(?:details|print|view|show|page|doc|gdetail|gdetailed).*\d+/\d+.*$', '', text, flags=re.MULTILINE|re.IGNORECASE)
    text = re.sub(r'^.*(?:mypanel|mpanel|panel|admin|dashboard).*$', '', text, flags=re.MULTILINE|re.IGNORECASE)
    
    # СУПЕР АГРЕССИВНЫЕ ПРАВИЛА ДЛЯ УДАЛЕНИЯ ТЕХНИЧЕСКИХ URL
    text = re.sub(r'^.*\d+\.\d+\.\d+\.\d+/\S+.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^.*print=1.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^.*\.php\?.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^.*\d+/\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^.*id=\d+.*$', '', text, flags=re.MULTILINE)
    
    # Удаляем строки с датами и номерами страниц
    text = re.sub(r'^\d{1,2}\.\d{1,2}\.\d{4},\s*\d{1,2}:\d{2}.*$', '', text, flags=re.MULTILINE)
    
    # ВТОРОЙ ПРОХОД: Более детальная очистка
    
    # Удаляем маркеры кода
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    
    # Удаляем строки, которые выглядят как заголовки языков программирования
    text = re.sub(r'^(python|java|javascript|html|css|bash|shell|sql|json|xml|yaml|cpp|c\+\+|c#|csharp|go|ruby|php|swift|kotlin|rust|typescript|dart|r|matlab|perl|scala|haskell|lua|julia|powershell|vba|fortran|assembly|objective-c|groovy|clojure|erlang|elixir|ocaml|f#|fsharp|scheme|racket|lisp|prolog|ada|cobol|pascal|delphi|abap|apex|vhdl|verilog|tcl|awk|sed|latex|markdown|restructuredtext|asciidoc|mediawiki|textile|org|creole|wiki|pod|rdoc|epytext|javadoc|doxygen|sphinx|jsdoc|yard|natural language|text|code):?\s*$', '', text, flags=re.IGNORECASE|re.MULTILINE)
    
    # Удаляем строки, содержащие URL-подобные пути
    text = re.sub(r'^.*task/person/details\.php\?.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^.*mypanel/task/person/details\.php\?.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^.*\.php\?.*\d+/\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^.*\.php\?.*$', '', text, flags=re.MULTILINE)
    
    # Удаляем IP-адреса с путями
    text = re.sub(r'\b\d+\.\d+\.\d+\.\d+/\S+', '', text)
    text = re.sub(r'^.*\d+\.\d+\.\d+\.\d+/.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\d+\.\d+\.\d+\s*$', '', text, flags=re.MULTILINE)
    
    # Удаляем номера страниц и другие технические метки
    text = re.sub(r'\s*\d+/\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b\d+/\d+\b', '', text)  # Удаляем все вхождения формата X/Y в тексте
    
    # Удаляем строки, которые выглядят как технические заголовки или метаданные
    text = re.sub(r'^(Document ID|File Name|Created Date|Modified Date|Author|Owner|Tags|Keywords|Description|Title|Subject|Category|Format|Language|Size|Pages|Words|Characters|Lines|Paragraphs|Version|Status|Security|Comments|Company|Manager|Content Type|Last Modified By|Revision Number|Total Editing Time|Template|Application|Doc Security|Scale|Links Up-to-date|Shared Doc|HyperlinksChanged|LinksUpToDate|ScaleCrop|HeadingPairs|TitlesOfParts):.*$', '', text, flags=re.IGNORECASE|re.MULTILINE)
    
    # Удаляем строки, содержащие только цифры, слэши и пробелы
    text = re.sub(r'^\s*[\d\s/]+\s*$', '', text, flags=re.MULTILINE)
    
    # ТРЕТИЙ ПРОХОД: Финальная очистка
    
    # Удаляем общие URL (после сохранения полезных)
    text = re.sub(r'https?://\S+', '', text)
    
    # Удаляем любые оставшиеся строки с номерами страниц
    text = re.sub(r'.*\d+/\d+\s*$', '', text, flags=re.MULTILINE)
    
    # Удаляем строки, содержащие только числа и пробелы
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    
    # ЧЕТВЕРТЫЙ ПРОХОД: Экстра-агрессивная очистка для конкретных шаблонов
    
    # Удаляем любые строки, содержащие IP-адреса и технические URL
    lines = text.split('\n')
    filtered_lines = []
    
    for line in lines:
        # Пропускаем строки с IP-адресами
        if re.search(r'\d+\.\d+\.\d+\.\d+', line):
            continue
        
        # Пропускаем строки с техническими URL
        if re.search(r'(?:\.php\?|\.asp\?|\.jsp\?|\.aspx\?)', line):
            continue
            
        # Пропускаем строки с параметрами print=1 или id=
        if re.search(r'(?:print=1|id=\d+)', line):
            continue
            
        # Пропускаем строки с номерами страниц в конце
        if re.search(r'\d+/\d+\s*$', line):
            continue
            
        # Пропускаем строки с mypanel, panel, task и т.д.
        if re.search(r'(?:mypanel|mpanel|panel|task/person|details)', line, re.IGNORECASE):
            continue
            
        # Добавляем строку, если она прошла все проверки
        filtered_lines.append(line)
    
    # Собираем текст обратно
    text = '\n'.join(filtered_lines)
    
    # Удаляем повторяющиеся пустые строки
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Добавляем полезные ссылки обратно в текст
    if useful_links:
        text += "\n\nПрофессиональные ссылки:\n"
        for link in set(useful_links):  # Используем set для удаления дубликатов
            text += f"{link}\n"
    
    return text.strip()

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
        Ты - опытный HR-аналитик с 15-летним опытом найма в международных компаниях. У тебя высокие стандарты оценки кандидатов, ты не терпишь посредственности и всегда даешь честную и прямую оценку. Твоя задача - провести глубокий анализ кандидата и дать объективную оценку его соответствия требованиям вакансии.

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
        Пол: {candidate.base_answers.get('gender', 'Не указано') if candidate.base_answers else 'Не указано'}
        {f"Кандидат ранее подавался на позиции: {candidate.previous_applications}" if hasattr(candidate, 'previous_applications') and candidate.previous_applications else ""}

        Профессиональные вопросы и ответы (Очень важно учитывать эти ответы при оценке):
        {professional_answers}

        Вопросы о soft skills и ответы (Очень важно учитывать эти ответы при оценке):
        {soft_skills_answers}

        РЕЗЮМЕ КАНДИДАТА:
        {candidate.resume_text[:10000] if candidate.resume_text else 'Не предоставлено'}

        {f"СОПРОВОДИТЕЛЬНОЕ ПИСЬМО:\n{candidate.cover_letter[:3000]}" if candidate.cover_letter else ""}
        
        СТРУКТУРИРОВАННЫЕ ДАННЫЕ ИЗ РЕЗЮМЕ:
        {json.dumps(candidate.structured_resume_data, ensure_ascii=False, indent=2) if hasattr(candidate, 'structured_resume_data') and candidate.structured_resume_data else "Нет структурированных данных"}

        ВАЖНО - ЯЗЫКОВЫЕ НАВЫКИ:
        Внимательно проанализируй текст резюме на наличие информации о языковых навыках. Обязательно найди в резюме секции с названиями "Знание языков", "Языки", "Владение языками", "Languages", "Language skills" и т.п. 
        Если такая информация есть в резюме, обязательно учти её в оценке языковых навыков и явно укажи найденную информацию в комментарии к оценке языковых навыков.
        Если информация о языках не найдена, укажи это как недостаток в данных кандидата.
        
        ВАЖНО - ПРОВЕРКА СООТВЕТСТВИЯ ПОЛА:
        Проверь соответствие пола кандидата в резюме и в базовых вопросах. Обрати внимание на имя кандидата, используемые местоимения в резюме, и указанный пол в базовой информации.
        Если есть несоответствие, это должно быть отмечено как серьезное несоответствие данных в разделе "Несоответствия данных".
        
        ВАЖНО - ПРЕОБРАЗОВАНИЕ КОДОВ ПОЛА:
        При указании несоответствий в данных, всегда преобразуй коды пола в человекочитаемые значения:
        - '1' или 1 → "Мужской"
        - '2' или 2 → "Женский"
        - '0' или 0 или отсутствие значения → "Не указан"
        
        Например, вместо "Несоответствие пола: в базовой информации указан пол '1'" пиши "Несоответствие пола: в базовой информации указан пол 'Мужской'".

        ПРОВЕРКА ПОЛНОТЫ ДАННЫХ:
        В первую очередь определи, достаточно ли информации для адекватной оценки кандидата. Обязательными полями считаются:
        - Базовая информация о кандидате (ФИО, опыт работы)
        - Либо резюме, либо ответы на профессиональные вопросы

        Если данных недостаточно, укажи это в результате анализа и предложи, какую дополнительную информацию необходимо запросить.

        ПРОВЕРКА СООТВЕТСТВИЯ ДАННЫХ:
        Обязательно проверь соответствие данных между резюме и ответами кандидата:
        - Соответствие пола в резюме и в базовой информации (особенно внимательно)
        - Соответствие местоположения в резюме и в базовой информации
        - Соответствие образования в резюме и в базовой информации
        - Соответствие опыта работы в резюме и в базовой информации
        - Соответствие языковых навыков в резюме и в ответах

        Если обнаружены несоответствия, это должно быть явно указано в разделе "Несоответствия данных" (data_consistency.inconsistencies) и учтено при общей оценке кандидата как серьезный негативный фактор.

        ОЦЕНКА КАЧЕСТВА ИНФОРМАЦИИ:
        Проанализируй детализацию и качество предоставленных данных:
        - Оцени полноту и детализацию резюме
        - Проверь качество ответов на вопросы (развернутые vs поверхностные)
        - Проверь грамматику и стиль ответов
        - Оцени длину ответов (слишком короткие ответы считаются низкокачественными)
        - Оцени наличие признаков генерации контента с помощью ИИ

        ОПРЕДЕЛЕНИЕ ГЕНЕРАЦИИ ТЕКСТА ИИ:
        Тщательно проанализируй ответы кандидата на признаки генерации с помощью ИИ:
        - Шаблонные фразы и обороты, характерные для ИИ
        - Слишком идеальная структура ответов
        - Отсутствие личных деталей или конкретики
        - Общие фразы вместо конкретных примеров
        - Повторяющиеся речевые паттерны

        Дай оценку вероятности генерации текста с помощью ИИ в процентах (от 0 до 100), где:
        - 0-30%: Вероятно написано человеком
        - 30-50%: Есть некоторые признаки использования ИИ
        - 50-70%: Значительные признаки использования ИИ
        - 70-100%: Почти наверняка сгенерировано ИИ

        Если вероятность генерации ИИ превышает 50%, это должно считаться серьезным стоп-фактором.

        Если ответы слишком короткие (менее 20 слов), содержат грамматические ошибки или выглядят сгенерированными ИИ, это должно быть отмечено как проблема в разделе "Качество предоставленной информации".

        Оцени соответствие кандидата требованиям вакансии по следующим критериям:
        1. Местоположение (от 0 до 100) - ВАЖНО: даже если кандидат из Ашхабада и вакансия в Ашхабаде, оценка должна быть не выше 50, так как это нейтральный фактор
        2. Опыт работы (от 0 до 100)
        3. Технические навыки (от 0 до 100)
        4. Образование (от 0 до 100)
        5. Soft skills (от 0 до 100)
        6. Мотивация и соответствие ценностям компании (от 0 до 100)
        7. Стабильность трудовой истории (от 0 до 100)
        8. Актуальность профессионального опыта (от 0 до 100)
        9. Языковые навыки (от 0 до 100) - если указаны в резюме или требованиях вакансии
        10. Зарплатные ожидания (от 0 до 100) - насколько соответствуют возможностям компании

        Для каждого критерия напиши развернутый комментарий (не менее 2-3 предложений), объясняющий оценку.
        
        ВАЖНО: Убедись, что между оценками и комментариями нет противоречий. Если в комментарии указано, что кандидат владеет языком, оценка не может быть 0/100.

        ВАЖНО: Географическое соответствие (местоположение) считай нейтральным фактором, НЕ включай его в список сильных сторон кандидата. Это базовое условие, а не преимущество. Максимальная оценка за местоположение - 50 баллов.

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

        ОЦЕНКА КАЧЕСТВА ОТВЕТОВ:
        Оцени качество ответов кандидата по следующим параметрам (для каждого параметра дай развернутую оценку в 1-2 предложения):
        - Развернутость (подробные vs односложные)
        - Релевантность (насколько ответ соответствует вопросу)
        - Грамотность (наличие грамматических/орфографических ошибок)
        - Логичность и структурированность
        - Признаки генерации текста с помощью ИИ

        Составь:
        - Список сильных сторон кандидата (не более 5 пунктов)
        - Список нейтральных факторов (таких как местоположение)
        - Список слабых сторон или несоответствий требованиям (не более 5 пунктов)
        - Список несоответствий между данными резюме и ответами кандидата (если есть)
        - Общую рекомендацию: пригласить на собеседование, отклонить или запросить дополнительную информацию (развернутая рекомендация, не менее 3-4 предложений с обоснованием)
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
        - Серьезные несоответствия между данными в резюме и ответами
        - Признаки недостоверности предоставленной информации
        - Вероятность генерации ответов с помощью ИИ более 50%
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
                "data_quality_assessment": "Подробная оценка качества данных, не менее 2-3 предложений",
                "ai_generated_content_signs": true/false,
                "ai_generated_content_probability": число от 0 до 100,
                "low_quality_answers": true/false,
                "answer_quality_issues": ["проблема 1", "проблема 2", ...] или []
            }},
            "data_consistency": {{
                "consistent": true/false,
                "inconsistencies": ["несоответствие 1", "несоответствие 2", ...] или [],
                "severity": "низкая/средняя/высокая",
                "trust_score": число от 0 до 100
            }},
            "match_percent": число от 0 до 100,
            "confidence_score": число от 0 до 100, // насколько уверен в оценке на основе полноты данных
            "pros": ["сильная сторона 1", "сильная сторона 2", ...],
            "neutral_factors": ["нейтральный фактор 1", "нейтральный фактор 2", ...],
            "cons": ["слабая сторона 1", "слабая сторона 2", ...],
            "recommendation": "Развернутая рекомендация с обоснованием, не менее 3-4 предложений",
            "scores": {{
                "location": число от 0 до 50, // максимум 50 для локации
                "experience": число от 0 до 100,
                "tech_skills": число от 0 до 100,
                "education": число от 0 до 100,
                "soft_skills": число от 0 до 100,
                "motivation_and_values": число от 0 до 100,
                "employment_stability": число от 0 до 100,
                "experience_relevance": число от 0 до 100,
                "language_skills": число от 0 до 100,
                "salary_expectations": число от 0 до 100
            }},
            "score_comments": {{
                "location": "Развернутый комментарий о соответствии местоположения, 2-3 предложения",
                "experience": "Развернутый комментарий об опыте работы, 2-3 предложения",
                "tech_skills": "Развернутый комментарий о технических навыках, 2-3 предложения",
                "education": "Развернутый комментарий об образовании, 2-3 предложения",
                "soft_skills": "Развернутый комментарий о мягких навыках, 2-3 предложения",
                "motivation_and_values": "Развернутый комментарий о мотивации и соответствии ценностям, 2-3 предложения",
                "employment_stability": "Развернутый комментарий о стабильности трудовой истории, 2-3 предложения",
                "experience_relevance": "Развернутый комментарий о релевантности опыта, 2-3 предложения",
                "language_skills": "Развернутый комментарий о языковых навыках, 2-3 предложения",
                "salary_expectations": "Развернутый комментарий о соответствии зарплатных ожиданий, 2-3 предложения"
            }},
            "answer_quality": {{
                "overall_quality": "Подробная оценка общего качества ответов, не менее 2-3 предложений",
                "verbosity": "Подробная оценка развернутости ответов, не менее 1-2 предложений",
                "relevance": "Подробная оценка релевантности ответов, не менее 1-2 предложений",
                "grammar": "Подробная оценка грамотности ответов, не менее 1-2 предложений",
                "structure": "Подробная оценка структурированности ответов, не менее 1-2 предложений",
                "ai_generation_signs": true/false,
                "ai_generation_probability": число от 0 до 100
            }},
            
            ВАЖНО - ФОРМАТИРОВАНИЕ ПОЛЕЙ КАЧЕСТВА ОТВЕТОВ:
            Для полей в секции answer_quality начинай каждое поле с ключевого слова, характеризующего оценку:
            - overall_quality: начинай с "Высокое: ", "Среднее: " или "Низкое: "
            - verbosity: начинай с "Подробные: ", "Краткие: " или "Односложные: "
            - relevance: начинай с "Релевантные: ", "Частично релевантные: " или "Нерелевантные: "
            - grammar: начинай с "Грамотные: ", "С ошибками: " или "Неграмотные: "
            - structure: начинай с "Структурированные: ", "Частично структурированные: " или "Хаотичные: "
            
            Это необходимо для правильного отображения цветовых индикаторов в интерфейсе.
            
            "skills_breakdown": {{
                "key_skills": ["навык 1", "навык 2", ...],
                "additional_skills": ["навык 1", "навык 2", ...],
                "missing_skills": ["навык 1", "навык 2", ...]
            }},
            "career_dynamics": {{
                "growth_rate": "Подробное описание скорости роста, не менее 2-3 предложений",
                "avg_tenure": "средняя продолжительность на одном месте в годах",
                "stability_assessment": "Подробная оценка стабильности, не менее 2-3 предложений",
                "career_gaps": ["период 1: причина", "период 2: причина", ...] или []
            }},
            "special_cases": {{
                "career_switch": true/false,
                "mixed_employment": true/false,
                "frequent_job_changes": true/false,
                "visa_support_required": true/false,
                "repeated_application": true/false,
                "details": "Подробное описание особых обстоятельств, если есть, не менее 2-3 предложений"
            }},
            "inconsistencies": ["несоответствие 1", "несоответствие 2", ...] или [],
            "mismatch_notes": "Подробный текст о несоответствиях требованиям, если есть, не менее 2-3 предложений",
            "interview_questions": ["вопрос 1", "вопрос 2", ...],
            "urgency_rating": число от 1 до 5,
            "stop_factors": ["стоп-фактор 1", "стоп-фактор 2", ...] или [],
            "hidden_potential": {{
                "non_obvious_skills": ["навык 1", "навык 2", ...],
                "adaptability_assessment": "Подробная оценка адаптивности, не менее 2-3 предложений",
                "communication_skills": "Подробная оценка коммуникативных навыков, не менее 2-3 предложений"
            }},
            "long_term_outlook": {{
                "motivation_sustainability": "Подробный прогноз долгосрочной мотивации, не менее 2-3 предложений",
                "growth_potential": "Подробная оценка потенциала роста в компании, не менее 2-3 предложений"
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
        
        # Логируем полученный результат для отладки
        current_app.logger.info(f"Результат AI-анализа для кандидата ID={candidate.id}: {json.dumps(result, ensure_ascii=False)[:500]}...")
        
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
        
        # Сохраняем информацию о несоответствиях данных
        data_consistency = result.get('data_consistency', {})
        if hasattr(candidate, 'ai_data_consistency'):
            # Убедимся, что несоответствия представлены в виде списка
            if 'inconsistencies' in data_consistency and not isinstance(data_consistency['inconsistencies'], list):
                if isinstance(data_consistency['inconsistencies'], str):
                    data_consistency['inconsistencies'] = [data_consistency['inconsistencies']]
                else:
                    data_consistency['inconsistencies'] = []
            
            # Если несоответствий нет, добавим пустой список
            if 'inconsistencies' not in data_consistency:
                data_consistency['inconsistencies'] = []
                
            # Добавим уровень серьезности, если его нет
            if 'severity' not in data_consistency:
                data_consistency['severity'] = 'низкая' if not data_consistency.get('inconsistencies') else 'средняя'
                
            # Добавим уровень доверия, если его нет
            if 'trust_score' not in data_consistency:
                data_consistency['trust_score'] = 100 if not data_consistency.get('inconsistencies') else 70
                
            candidate.ai_data_consistency = data_consistency
        
        # Сохраняем информацию о качестве ответов
        answer_quality = result.get('answer_quality', {})
        if hasattr(candidate, 'ai_answer_quality'):
            # Убедимся, что у нас есть все необходимые поля
            if 'ai_generation_probability' not in answer_quality:
                answer_quality['ai_generation_probability'] = 0
                
            if 'ai_generation_signs' not in answer_quality:
                answer_quality['ai_generation_signs'] = False
                
            if 'overall_quality' not in answer_quality:
                answer_quality['overall_quality'] = 'среднее'
                
            candidate.ai_answer_quality = answer_quality
        
        # Сохраняем информацию о полноте данных
        data_completeness = result.get('data_completeness', {})
        if hasattr(candidate, 'ai_data_completeness'):
            # Убедимся, что проблемы с качеством ответов представлены в виде списка
            if 'answer_quality_issues' in data_completeness and not isinstance(data_completeness['answer_quality_issues'], list):
                if isinstance(data_completeness['answer_quality_issues'], str):
                    data_completeness['answer_quality_issues'] = [data_completeness['answer_quality_issues']]
                else:
                    data_completeness['answer_quality_issues'] = []
            
            # Если проблем нет, добавим пустой список
            if 'answer_quality_issues' not in data_completeness:
                data_completeness['answer_quality_issues'] = []
                
            # Добавим флаг низкого качества ответов, если его нет
            if 'low_quality_answers' not in data_completeness:
                data_completeness['low_quality_answers'] = len(data_completeness.get('answer_quality_issues', [])) > 0
                
            candidate.ai_data_completeness = data_completeness
        
        # Сохраняем дополнительные поля в JSON-поле, если оно есть
        if hasattr(candidate, 'ai_analysis_data'):
            candidate.ai_analysis_data = {
                'data_consistency': data_consistency,
                'answer_quality': answer_quality,
                'data_completeness': data_completeness,
                'skills_breakdown': result.get('skills_breakdown', {}),
                'career_dynamics': result.get('career_dynamics', {}),
                'special_cases': result.get('special_cases', {}),
                'hidden_potential': result.get('hidden_potential', {}),
                'long_term_outlook': result.get('long_term_outlook', {}),
                'stop_factors': result.get('stop_factors', []),
                'interview_questions': result.get('interview_questions', []),
                'inconsistencies': result.get('inconsistencies', []),
                'scores': scores,
                'score_comments': score_comments
            }
        
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
            model="gpt-4o",
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

def generate_vacancy_with_ai(title, employment_type, description_tasks, description_conditions):
    """
    Генерирует полные данные вакансии с помощью OpenAI API на основе базовой информации
    
    Args:
        title (str): Название вакансии
        employment_type (str): Тип занятости
        description_tasks (str): Базовое описание задач
        description_conditions (str): Базовые условия работы
        
    Returns:
        dict: Словарь с сгенерированными данными для вакансии или None в случае ошибки
    """
    try:
        # Получаем API ключ из конфигурации или переменных окружения
        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            api_key = os.environ.get('OPENAI_API_KEY')
            
        # Проверяем валидность ключа
        if not api_key or "your-" in api_key or len(api_key.strip()) < 20:
            current_app.logger.error("OpenAI API ключ невалидный или отсутствует")
            return None
        
        # Создаем клиента OpenAI
        client = OpenAI(api_key=api_key)
        
        # Формируем запрос к API
        prompt = f"""
        Ты - опытный HR-специалист, который помогает создать профессиональную вакансию. 
        Используй предоставленную информацию для создания полной и привлекательной вакансии.
        
        Базовая информация:
        - Название вакансии: {title}
        - Тип занятости: {employment_type}
        - Описание задач: {description_tasks}
        - Условия работы: {description_conditions}
        
        Создай следующие разделы:
        1. Улучшенное название вакансии (если нужно)
        2. Подробное описание задач с форматированием (маркированные списки, абзацы)
        3. Расширенные условия работы с форматированием
        4. Описание идеального кандидата (требования, навыки, опыт)
        5. 7 профессиональных вопросов для кандидата
        6. 7 вопросов на soft skills
        
        Формат ответа должен быть в виде JSON:
        {{
            "title": "Улучшенное название вакансии",
            "description_tasks": "Подробное описание задач",
            "description_conditions": "Расширенные условия работы",
            "ideal_profile": "Описание идеального кандидата",
            "questions": [
                {{"id": 1, "text": "Вопрос 1", "type": "text"}},
                {{"id": 2, "text": "Вопрос 2", "type": "text"}},
                ...
            ],
            "soft_questions": [
                {{"id": 1, "text": "Вопрос 1", "type": "text"}},
                {{"id": 2, "text": "Вопрос 2", "type": "text"}},
                ...
            ]
        }}
        
        Важно:
        - Используй форматирование текста (маркированные списки, абзацы)
        - Вопросы должны быть релевантными для данной вакансии
        - Все поля должны быть на русском языке
        - Ответ должен быть только в формате JSON без дополнительного текста
        """
        
        # Отправляем запрос к OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты - опытный HR-специалист, который создает профессиональные вакансии. Твой ответ должен быть в формате JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        # Получаем ответ
        result = response.choices[0].message.content
        
        # Проверяем, что ответ содержит валидный JSON
        # Ищем JSON в ответе (на случай, если модель добавила лишний текст)
        import re
        json_match = re.search(r'({[\s\S]*})', result)
        if json_match:
            result = json_match.group(1)
        
        # Парсим JSON
        try:
            vacancy_data = json.loads(result)
            
            # Проверяем наличие всех необходимых полей
            required_fields = ['title', 'description_tasks', 'description_conditions', 'ideal_profile', 'questions', 'soft_questions']
            for field in required_fields:
                if field not in vacancy_data:
                    current_app.logger.warning(f"В ответе API отсутствует поле {field}")
                    # Если поле отсутствует, добавляем пустое значение
                    if field in ['questions', 'soft_questions']:
                        vacancy_data[field] = []
                    else:
                        vacancy_data[field] = ""
            
            # Проверяем и корректируем формат вопросов
            for question_type in ['questions', 'soft_questions']:
                if not isinstance(vacancy_data[question_type], list):
                    vacancy_data[question_type] = []
                else:
                    # Проверяем каждый вопрос и добавляем id и type, если их нет
                    for i, q in enumerate(vacancy_data[question_type]):
                        if isinstance(q, str):
                            # Если вопрос - это просто строка, преобразуем его в словарь
                            vacancy_data[question_type][i] = {"id": i+1, "text": q, "type": "text"}
                        elif isinstance(q, dict):
                            # Если вопрос - словарь, проверяем наличие необходимых полей
                            if 'id' not in q:
                                q['id'] = i+1
                            if 'text' not in q:
                                q['text'] = f"Вопрос {i+1}"
                            if 'type' not in q:
                                q['type'] = "text"
            
            # Ограничиваем количество вопросов до 7
            if len(vacancy_data['questions']) > 7:
                vacancy_data['questions'] = vacancy_data['questions'][:7]
            if len(vacancy_data['soft_questions']) > 7:
                vacancy_data['soft_questions'] = vacancy_data['soft_questions'][:7]
                
        except json.JSONDecodeError:
            current_app.logger.error(f"Не удалось распарсить JSON из ответа API: {result[:500]}")
            return None
        
        # Логируем успешную генерацию
        current_app.logger.info(f"Успешно сгенерирована вакансия с помощью AI: {vacancy_data['title']}")
        
        return vacancy_data
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при генерации вакансии с помощью AI: {str(e)}")
        return None