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
from app import db
from app.models.candidate import Candidate

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
                if not response.choices or not response.choices[0].message.content:
                    current_app.logger.error(f"Пустой ответ от OpenAI API для страницы {page_num + 1}")
                    continue
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
    """Обработка резюме и запуск анализа"""
    try:
        # Получаем кандидата
        candidate = Candidate.query.get(candidate_id)
        if not candidate:
            current_app.logger.error(f"Кандидат не найден: {candidate_id}")
            return
        
        # Проверяем наличие файла резюме
        if not resume_path or not os.path.exists(resume_path):
            current_app.logger.error(f"Файл резюме не найден: {resume_path}")
            return
        
        # Извлекаем текст из резюме
        result = extract_resume_text(resume_path)
        if not result:
            current_app.logger.error(f"Не удалось извлечь текст из резюме: {resume_path}")
            return
        
        # Очищаем текст резюме
        cleaned_text = clean_resume_text(result['text'])
        
        # Обновляем данные кандидата
        candidate.resume_text = cleaned_text
        if 'structured_data' in result:
            candidate.structured_resume_data = result['structured_data']
        
        # Сохраняем изменения
        db.session.commit()
        
        # Запускаем AI-анализ
        job_id = request_ai_analysis(candidate)
        if job_id:
            current_app.logger.info(f"Запущен AI-анализ для кандидата {candidate_id}, job_id: {job_id}")
        else:
            current_app.logger.error(f"Не удалось запустить AI-анализ для кандидата {candidate_id}")
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при обработке резюме: {str(e)}")
        db.session.rollback()
        raise

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
        Ты - опытный HR-аналитик с 25-летним опытом найма в международных компаниях. У тебя высокие стандарты оценки кандидатов, ты не терпишь посредственности и всегда даешь честную и прямую оценку. Твоя задача - провести глубокий анализ кандидата и дать объективную оценку его соответствия требованиям вакансии.

        ПРОТОКОЛ ОБРАБОТКИ НЕПОЛНЫХ ДАННЫХ:

        Определи категорию полноты данных:
        1. КРИТИЧЕСКАЯ НЕДОСТАТОЧНОСТЬ (требует немедленного прекращения анализа)
           - Отсутствие ФИО кандидата
           - Отсутствие И резюме, И ответов на профессиональные вопросы
           
           ДЕЙСТВИЕ: Прекрати анализ, верни только поле "data_completeness" с указанием критической недостаточности данных

        2. СУЩЕСТВЕННАЯ НЕДОСТАТОЧНОСТЬ (сильно влияет на надежность оценки)
           - Отсутствие резюме при наличии только кратких ответов на вопросы
           - Отсутствие ответов на профессиональные вопросы при кратком резюме
           - Отсутствие информации об опыте работы
           
           ДЕЙСТВИЕ: Проведи ограниченный анализ с пометкой "low_confidence" и укажи confidence_score не выше 40%

        3. ЧАСТИЧНАЯ НЕДОСТАТОЧНОСТЬ (снижает надежность оценки по отдельным параметрам)
           - Отсутствие ответов на отдельные вопросы
           - Неполное резюме с базовой информацией
           - Отсутствие информации об образовании/языках/зарплатных ожиданиях
           
           ДЕЙСТВИЕ: Проведи полный анализ с confidence_score не выше 70% и четко укажи, каких данных не хватает

        4. АДЕКВАТНАЯ ПОЛНОТА (позволяет провести достоверную оценку)
           - Наличие всех основных элементов (базовая информация, резюме, ответы на ключевые вопросы)
           - Допустимы некоторые второстепенные пропуски
           
           ДЕЙСТВИЕ: Проведи полный анализ, confidence_score до 90%

        5. ПОЛНАЯ ИНФОРМАЦИЯ (идеальный случай)
           - Наличие всей запрашиваемой информации
           
           ДЕЙСТВИЕ: Проведи полный анализ, confidence_score до 100%

        АЛГОРИТМ ПРОВЕРКИ ПОЛНОТЫ ДАННЫХ:

        1. Проверь наличие обязательных полей:
           a. ФИО кандидата
           b. Информация об опыте работы
           c. Либо резюме, либо структурированные ответы на профессиональные вопросы
           
        2. Проверь наличие рекомендуемых полей:
           a. Образование
           b. Ответы на вопросы о soft skills
           c. Зарплатные ожидания
           d. Сведения о языковых навыках
           
        3. Проверь качество предоставленных данных:
           a. Минимальная длина ответов на вопросы (не менее 20 слов)
           b. Минимальный объем резюме (не менее 200 слов)
           c. Структурированность и читаемость данных
           
        4. Для каждого отсутствующего поля определи:
           a. Критичность для анализа
           b. Возможность косвенного получения информации из других полей
           c. Влияние на достоверность итоговой оценки

        5. Рассчитай процент полноты данных:
           a. Обязательные поля: 70% значимости
           b. Рекомендуемые поля: 30% значимости
           c. Формула расчета: (заполненные_обязательные_поля/всего_обязательных_полей)*0.7 + (заполненные_рекомендуемые_поля/всего_рекомендуемых_полей)*0.3

        6. Определи категорию полноты данных согласно проценту:
           a. 0-30%: КРИТИЧЕСКАЯ НЕДОСТАТОЧНОСТЬ
           b. 31-60%: СУЩЕСТВЕННАЯ НЕДОСТАТОЧНОСТЬ
           c. 61-80%: ЧАСТИЧНАЯ НЕДОСТАТОЧНОСТЬ
           d. 81-95%: АДЕКВАТНАЯ ПОЛНОТА
           e. 96-100%: ПОЛНАЯ ИНФОРМАЦИЯ

        ПРОТОКОЛ ИМПУТАЦИИ ДАННЫХ:

        При обнаружении отсутствующих данных, следуй этим принципам:

        1. ОПЫТ РАБОТЫ:
           - Если отсутствует в базовой информации, но есть в резюме: извлечь из резюме
           - Если отсутствует полностью: установить confidence_score для experience не выше 20%
           
        2. ОБРАЗОВАНИЕ:
           - Если отсутствует в базовой информации, но есть в резюме: извлечь из резюме
           - Если отсутствует полностью: установить нейтральную оценку (50/100) с пометкой "данные отсутствуют"
           
        3. ЯЗЫКОВЫЕ НАВЫКИ:
           - Если в резюме есть индикаторы владения языками (международный опыт, публикации): сделать предположение с низкой уверенностью
           - Если нет никаких индикаторов: установить language_skills в "не указано" и оценку 0/100
           
        4. ЗАРПЛАТНЫЕ ОЖИДАНИЯ:
           - Если не указаны: исключить из расчета общей оценки и указать "не влияет на оценку"
           
        5. SOFT SKILLS:
           - Если отсутствуют ответы на вопросы о soft skills: попытаться извлечь из резюме и сопроводительного письма
           - Если данных недостаточно: снизить уверенность в оценке soft_skills до 40%
           
        6. МОТИВАЦИЯ:
           - Если отсутствует сопроводительное письмо и ответы на вопросы о мотивации: снизить уверенность в оценке motivation_and_values до 30%
           - Если есть косвенные индикаторы: сделать предположение с низкой уверенностью

        ВАЖНО: Любая импутация данных должна быть явно отмечена с указанием того, что информация была получена косвенным путем, а не предоставлена напрямую кандидатом.

        АЛГОРИТМ ДИНАМИЧЕСКОЙ КОРРЕКТИРОВКИ ВЕСОВ:

        При отсутствии данных для определенных критериев оценки:

        1. Определи отсутствующие или низкокачественные критерии, для которых невозможно дать надежную оценку
        2. Исключи эти критерии из расчета общей оценки
        3. Перераспредели веса оставшихся критериев пропорционально их исходной значимости
        4. Формула пересчета для каждого оставшегося критерия:
           новый_вес = исходный_вес * (100 / сумма_весов_оставшихся_критериев)

        5. Примени следующие правила перераспределения:
           a. При отсутствии данных о soft_skills: увеличь вес tech_skills и experience
           b. При отсутствии данных о tech_skills: увеличь вес experience и education
           c. При отсутствии данных об образовании: увеличь вес experience и tech_skills
           d. При отсутствии данных о языковых навыках: исключи из расчета без перераспределения
           e. При отсутствии данных о зарплатных ожиданиях: исключи из расчета без перераспределения

        6. Сохрани в результате оба набора весов:
           a. original_weights: исходная система весов
           b. adjusted_weights: скорректированная система весов

        АЛГОРИТМ КОНТЕКСТНОГО ВОССТАНОВЛЕНИЯ ДАННЫХ:

        При обнаружении отсутствующих данных, применяй эти методы восстановления:

        1. ИЗВЛЕЧЕНИЕ ИЗ НЕСТАНДАРТНЫХ ИСТОЧНИКОВ:
           - Проверь сопроводительное письмо на наличие информации о навыках, опыте, образовании
           - Проанализируй ответы на любые вопросы на предмет косвенных упоминаний недостающей информации
           - Посмотри, можно ли извлечь информацию о языковых навыках из описания проектов/опыта

        2. РЕКОНСТРУКЦИЯ ОПЫТА:
           - Если не указана длительность работы на определенной позиции, но есть даты начала и окончания: рассчитай длительность
           - Если не указаны даты работы вообще: оцени примерный стаж по уровню занимаемых должностей и описанию обязанностей
           - Если нет структурированного описания опыта: извлеки информацию из общего текста резюме или ответов

        3. ОЦЕНКА НАВЫКОВ ПО КОСВЕННЫМ ПРИЗНАКАМ:
           - Если прямо не указаны технические навыки: выведи их из описания проектов и достижений
           - Если не указаны soft skills: проанализируй стиль коммуникации в ответах и резюме

        4. ВЕРИФИКАЦИЯ РЕКОНСТРУИРОВАННЫХ ДАННЫХ:
           - Для каждого реконструированного элемента укажи степень уверенности в реконструкции (низкая/средняя/высокая)
           - Укажи метод реконструкции и источник данных
           - Отметь реконструированные данные специальным маркером в выводах

        МАТРИЦА КРИТИЧНОСТИ ДАННЫХ ПО ТИПАМ ВАКАНСИЙ:

        Скорректируй важность различных типов данных в зависимости от типа вакансии:

        1. ТЕХНИЧЕСКИЕ ПОЗИЦИИ:
           - Критически важно: технические навыки, опыт работы, образование
           - Важно: резюме, ответы на технические вопросы
           - Желательно: soft skills, мотивация
           - Опционально: языковые навыки (если не указаны в требованиях)

        2. УПРАВЛЕНЧЕСКИЕ ПОЗИЦИИ:
           - Критически важно: опыт работы, soft skills, резюме
           - Важно: мотивация, языковые навыки, стабильность трудовой истории
           - Желательно: технические навыки, образование
           - Опционально: зарплатные ожидания

        3. ТВОРЧЕСКИЕ/КРЕАТИВНЫЕ ПОЗИЦИИ:
           - Критически важно: портфолио/примеры работ, резюме, soft skills
           - Важно: опыт работы, мотивация
           - Желательно: образование, языковые навыки
           - Опционально: зарплатные ожидания, стабильность трудовой истории

        4. НАЧАЛЬНЫЕ ПОЗИЦИИ:
           - Критически важно: образование, мотивация, soft skills
           - Важно: базовые технические навыки, резюме
           - Желательно: любой релевантный опыт, языковые навыки
           - Опционально: зарплатные ожидания, стабильность трудовой истории

        5. ПРОДАЖИ И РАБОТА С КЛИЕНТАМИ:
           - Критически важно: soft skills, опыт работы, мотивация
           - Важно: языковые навыки, стабильность трудовой истории
           - Желательно: образование, технические навыки
           - Опционально: зарплатные ожидания

        Примени соответствующую матрицу при оценке полноты данных в зависимости от типа вакансии.

        ПРОТОКОЛ ВЫЯВЛЕНИЯ УМЫШЛЕННОГО СОКРЫТИЯ ИНФОРМАЦИИ:

        Проверь следующие индикаторы возможного намеренного сокрытия информации:

        1. ХРОНОЛОГИЧЕСКИЕ ПРОБЕЛЫ:
           - Отсутствие информации о периодах длительностью более 6 месяцев в трудовой истории
           - Размытые формулировки дат ("начало 2018", "зима 2019" вместо конкретных месяцев)
           - Указание только годов без месяцев для коротких периодов работы

        2. ИЗБИРАТЕЛЬНАЯ ДЕТАЛИЗАЦИЯ:
           - Подробное описание одних позиций и минимальная информация о других
           - Отсутствие описания обязанностей для отдельных позиций
           - Непропорциональное внимание к давним позициям при скудности информации о недавних

        3. УКЛОНЧИВЫЕ ОТВЕТЫ:
           - Переформулирование вопроса в ответе без предоставления запрашиваемой информации
           - Общие фразы вместо конкретики в ответах на прямые вопросы
           - Перенаправление внимания на другие достижения/навыки при вопросе о конкретной компетенции

        4. ДЕЙСТВИЯ ПРИ ОБНАРУЖЕНИИ ПРИЗНАКОВ УМЫШЛЕННОГО СОКРЫТИЯ:
           - Укажи конкретные области, где предполагается сокрытие информации
           - Оцени потенциальное влияние на итоговую оценку кандидата
           - Сформулируй прямые вопросы для прояснения ситуации
           - Пометь как риск-фактор в общей оценке

        ПРОТОКОЛ АНАЛИЗА ЧАСТИЧНО ЗАПОЛНЕННОЙ АНКЕТЫ:

        Когда кандидат ответил только на часть вопросов, выполни следующий анализ:

        1. АНАЛИЗ ПАТТЕРНА ОТВЕТОВ:
           - Определи, какие категории вопросов были проигнорированы
           - Проверь, есть ли корреляция между сложностью вопросов и вероятностью ответа
           - Оцени, является ли паттерн ответов случайным или систематическим

        2. ИНТЕРПРЕТАЦИЯ ИЗБИРАТЕЛЬНОСТИ:
           - Если пропущены вопросы о негативном опыте/неудачах: возможно избегание сложных тем
           - Если пропущены вопросы, требующие конкретики: возможно отсутствие соответствующего опыта
           - Если пропущены простые/базовые вопросы: возможно недостаточная мотивация/внимательность

        3. ОЦЕНКА КАЧЕСТВА ИМЕЮЩИХСЯ ОТВЕТОВ:
           - Анализ глубины и детальности предоставленных ответов
           - Сравнение объема ответов на разные категории вопросов
           - Оценка соотношения конкретики и общих фраз

        4. ВЫВОДЫ О МОТИВАЦИИ:
           - Если заполнено менее 50% анкеты: рассматривать как потенциальный индикатор низкой мотивации
           - Если пропущены только сложные вопросы: возможный индикатор неготовности к сложным задачам
           - Если пропущены только необязательные поля: нейтральный индикатор

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

        ВАЖНО - КОРРЕКТИРОВКА ВЕСОВ ПО ТИПУ ВАКАНСИИ:
        В зависимости от категории вакансии, автоматически скорректируй веса критериев:
        - Для технических позиций: повышенный вес tech_skills и experience_relevance
        - Для управленческих позиций: повышенный вес soft_skills и experience
        - Для начальных позиций: повышенный вес education и motivation_and_values
        - Для креативных позиций: повышенный вес soft_skills и hidden_potential

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

        СИСТЕМА ВЕСОВЫХ КОЭФФИЦИЕНТОВ:
        weights = {{
            "location": 5,  # Наименьший вес, так как это базовое условие
            "experience": 20,  # Высокий вес для опыта работы
            "tech_skills": 25,  # Наибольший вес для технических навыков
            "education": 10,
            "soft_skills": 15,
            "motivation_and_values": 10,
            "employment_stability": 5,
            "experience_relevance": 20,  # Высокий вес для релевантности опыта
            "language_skills": 10,
            "salary_expectations": 5
        }}

        АЛГОРИТМ АДАПТИВНЫХ ВЕСОВ:
        Проанализируй текст вакансии и автоматически определи ключевые приоритеты:
        1. Подсчитай частоту упоминания различных компетенций и требований в тексте вакансии
        2. Определи процентное соотношение текста, посвященное разным аспектам (техническим навыкам, soft skills и т.д.)
        3. Выдели ключевые фразы, указывающие на приоритеты ("критически важно", "будет преимуществом", "обязательно")
        4. На основе этого анализа скорректируй базовые веса автоматически

        Сохрани как original_weights базовую систему весов и как adjusted_weights скорректированную.

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
        - Серьезные несоответствия между данными в резюме и ответах
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
            
            "criterion_confidence": {{
                "location": число от 0 до 100,
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
            "resume_quality_assessment": {{
                "completeness": число от 0 до 100,
                "structure_quality": число от 0 до 100,
                "detail_level": число от 0 до 100,
                "achievement_focus": число от 0 до 100,
                "quantifiable_results": число от 0 до 100,
                "chronological_integrity": число от 0 до 100,
                "formatting_consistency": число от 0 до 100,
                "missing_sections": ["список отсутствующих важных разделов"],
                "overall_resume_score": число от 0 до 100,
                "resume_improvement_recommendations": ["рекомендации по улучшению резюме"]
            }},
            "weighted_match_percent": "рассчитывается как сумма(score * weight) для каждого критерия, деленная на сумму весов",
            "quality_adjustment_factor": "число от 0.5 до 1.0, используемое для корректировки weighted_match_percent на основе data_completeness и data_consistency",
            "adjusted_match_percent": "weighted_match_percent * quality_adjustment_factor",
            "inconsistencies": ["несоответствие 1", "несоответствие 2", ...] или [],
            "mismatch_notes": "Подробный текст о несоответствиях требованиям, если есть, не менее 2-3 предложений",
            "interview_questions": ["вопрос 1", "вопрос 2", ...],
            "urgency_rating": число от 1 до 5,
            "stop_factors": ["стоп-фактор 1", "стоп-фактор 2", ...] или [],
            "stop_factors_priority": {{
                "critical": ["список критичных стоп-факторов, требующих немедленного отклонения"],
                "major": ["список серьезных стоп-факторов, требующих особого внимания"],
                "minor": ["список незначительных стоп-факторов, требующих обсуждения"]
            }},
            "hidden_potential": {{
                "non_obvious_skills": ["навык 1", "навык 2", ...],
                "adaptability_assessment": "Подробная оценка адаптивности, не менее 2-3 предложений",
                "communication_skills": "Подробная оценка коммуникативных навыков, не менее 2-3 предложений"
            }},
            "long_term_outlook": {{
                "motivation_sustainability": "Подробный прогноз долгосрочной мотивации, не менее 2-3 предложений",
                "growth_potential": "Подробная оценка потенциала роста в компании, не менее 2-3 предложений"
            }},
            "cultural_fit_analysis": {{
                "company_culture_keywords": ["извлечь ключевые слова из описания компании и ценностей"],
                "candidate_values_keywords": ["извлечь ключевые слова из ответов кандидата и резюме"],
                "alignment_matrix": [
                    {{
                        "company_value": "ценность компании",
                        "candidate_indicators": ["индикаторы в резюме/ответах"],
                        "alignment_score": число от 0 до 100,
                        "reasoning": "объяснение оценки в 1-2 предложения"
                    }},
                    // дополнительные ценности
                ],
                "cultural_fit_score": число от 0 до 100,
                "adaptation_prognosis": "прогноз адаптации к корпоративной культуре, 2-3 предложения"
            }},
            "internal_consistency_analysis": {{
                "cross_validation_checks": [
                    {{
                        "check_topic": "тема для проверки (например, 'опыт с технологией X')",
                        "source_1": "первое упоминание (документ/вопрос)",
                        "source_1_statement": "утверждение в первом источнике",
                        "source_2": "второе упоминание (документ/вопрос)",
                        "source_2_statement": "утверждение во втором источнике",
                        "contradiction_level": "нет/слабая/средняя/сильная",
                        "confidence": число от 0 до 100
                    }},
                    // дополнительные проверки
                ],
                "contradiction_summary": "сводка обнаруженных противоречий, 2-3 предложения",
                "credibility_impact": число от -50 до 0 (штраф к общему рейтингу)
            }},
            "success_prediction": {{
                "onboarding_estimation": {{
                    "expected_time_to_productivity": "оценка времени до полной производительности в неделях",
                    "learning_curve_factors": ["факторы, влияющие на кривую обучения"],
                    "risk_areas": ["возможные области затруднений"]
                }},
                "retention_probability": {{
                    "6_month": число от 0 до 100,
                    "1_year": число от 0 до 100,
                    "3_year": число от 0 до 100,
                    "factors_positive": ["факторы, повышающие вероятность удержания"],
                    "factors_negative": ["факторы, снижающие вероятность удержания"]
                }},
                "performance_potential": {{
                    "baseline_performance": "ожидаемый базовый уровень производительности, 1-2 предложения",
                    "growth_ceiling": "потолок роста производительности, 1-2 предложения",
                    "productivity_drivers": ["факторы, которые могут повысить производительность"],
                    "productivity_barriers": ["факторы, которые могут ограничить производительность"]
                }}
            }},
            "transferable_skills_analysis": {{
                "indirect_skill_indicators": ["индикаторы неявных навыков из резюме"],
                "skill_equivalency_mapping": [
                    {{
                        "mentioned_skill": "навык из резюме",
                        "equivalent_skills": ["эквивалентные навыки для позиции"],
                        "transferability_score": число от 0 до 100,
                        "context_transfer_notes": "объяснение того, как навык переносится в новый контекст"
                    }},
                    // дополнительные сопоставления
                ],
                "hidden_qualification_score": число от 0 до 100,
                "competency_gap_mitigation": "анализ того, как скрытые навыки могут компенсировать отсутствующие компетенции, 2-3 предложения"
            }},
            "career_timing_analysis": {{
                "career_stage_identification": "определение текущего этапа карьеры кандидата",
                "position_timing_alignment": "оценка соответствия времени подачи заявки карьерному циклу, 2-3 предложения",
                "growth_acceleration_periods": ["периоды ускоренного роста в карьере"],
                "plateau_periods": ["периоды замедления карьерного роста"],
                "career_momentum_score": число от 0 до 100,
                "trajectory_match": "оценка совпадения карьерной траектории кандидата с типичной траекторией для позиции, 2-3 предложения"
            }},
            "psycholinguistic_indicators": {{
                "language_complexity": "оценка сложности языка (простой/средний/сложный)",
                "detail_orientation": "анализ внимания к деталям на основе точности описаний, от 0 до 100",
                "narrative_structure": "анализ структуры повествования (линейная/разветвленная/хаотичная)",
                "self_presentation_style": "стиль самопрезентации (уверенный/нейтральный/скромный)",
                "communication_preference_indicators": ["индикаторы предпочтительного стиля коммуникации"],
                "analytical_thinking_markers": ["лингвистические маркеры аналитического мышления"],
                "emotional_intelligence_indicators": ["индикаторы эмоционального интеллекта"],
                "personality_trait_correlations": "соотношение с чертами личности, релевантными для позиции, 2-3 предложения"
            }},
            "professional_network_assessment": {{
                "industry_connection_indicators": ["индикаторы связей в индустрии"],
                "company_overlap_analysis": ["компании, в которых работали и кандидат, и текущие сотрудники"],
                "reference_potential": "оценка потенциала для получения качественных рекомендаций, 1-2 предложения",
                "knowledge_sharing_potential": "оценка потенциала обмена знаниями через профессиональную сеть, 1-2 предложения",
                "network_leverage_opportunities": ["возможности использования сети контактов для компании"],
                "network_capital_score": число от 0 до 100
            }},
            "interview_simulation": {{
                "predicted_responses": [
                    {{
                        "question": "стандартный вопрос собеседования для позиции",
                        "predicted_response_quality": "высокая/средняя/низкая",
                        "anticipated_strengths": ["сильные стороны ответа"],
                        "anticipated_weaknesses": ["слабые стороны ответа"],
                        "follow_up_recommendations": ["рекомендуемые уточняющие вопросы"]
                    }},
                    // дополнительные вопросы
                ],
                "overall_interview_readiness": число от 0 до 100,
                "interview_coaching_points": ["ключевые моменты для подготовки кандидата к собеседованию"]
            }},
            "comparative_analysis": {{
                "ideal_candidate_gap": "процентное отклонение от идеального профиля",
                "typical_successful_similarity": "процент сходства с типичным успешным профилем",
                "minimum_requirements_margin": "насколько кандидат превосходит минимальные требования",
                "differential_analysis": "детальный сравнительный анализ по основным параметрам, 3-4 предложения",
                "comparative_ranking_prediction": "прогноз ранга кандидата среди других потенциальных претендентов, 1-2 предложения"
            }},
            "candidate_uniqueness_analysis": {{
                "differentiation_factors": ["факторы, отличающие кандидата от типичных претендентов"],
                "unique_experience_combinations": ["уникальные комбинации опыта и навыков"],
                "rare_skill_clusters": ["редкие сочетания навыков"],
                "innovation_potential_indicators": ["индикаторы потенциала для инноваций"],
                "competitive_edge_assessment": "оценка конкурентного преимущества кандидата, 2-3 предложения",
                "usp_statement": "формулировка уникального предложения кандидата в 1-2 предложения"
            }},
            "energy_and_drive_assessment": {{
                "accomplishment_velocity": "скорость достижения результатов в предыдущих ролях",
                "initiative_indicators": ["индикаторы проявления инициативы"],
                "challenge_seeking_behaviors": ["индикаторы поиска сложных задач"],
                "persistence_patterns": ["паттерны настойчивости и преодоления трудностей"],
                "work_intensity_history": "история интенсивности работы и управления нагрузкой, 1-2 предложения",
                "energy_sustainability_assessment": "оценка устойчивости энергии и риска выгорания, 1-2 предложения",
                "drive_score": число от 0 до 100
            }},
            "decision_making_style_analysis": {{
                "analytical_vs_intuitive_balance": "соотношение аналитического и интуитивного подходов, от 0 до 100",
                "risk_approach": "отношение к риску (избегающий/нейтральный/принимающий)",
                "decision_speed": "скорость принятия решений (быстрая/средняя/медленная)",
                "data_dependence": "зависимость от данных при принятии решений (высокая/средняя/низкая)",
                "collaborative_vs_independent": "предпочтение коллаборативного или независимого принятия решений, от 0 до 100",
                "decision_style_match": "соответствие стиля принятия решений требованиям позиции, 2-3 предложения"
            }},
            "learning_agility_assessment": {{
                "knowledge_acquisition_patterns": ["паттерны приобретения новых знаний"],
                "skill_development_velocity": "скорость развития навыков на основе карьерной истории",
                "adaptation_evidence": ["свидетельства успешной адаптации к новым условиям"],
                "continuous_education_history": "история непрерывного образования и развития, 1-2 предложения",
                "learning_style_indicators": ["индикаторы предпочтительного стиля обучения"],
                "teachability_score": число от 0 до 100,
                "learning_curve_prediction": "прогноз кривой обучения для данной позиции, 2-3 предложения"
            }},
            "productivity_indicators": {{
                "achievement_density": "плотность достижений на единицу времени работы",
                "outcome_orientation_score": "ориентация на результат, от 0 до 100",
                "efficiency_signals": ["сигналы эффективности в описании опыта"],
                "resource_optimization_history": "история оптимизации ресурсов, 1-2 предложения",
                "bottleneck_resolution_capability": "способность решать проблемы узких мест, 1-2 предложения",
                "productivity_prognosis": "прогноз продуктивности на данной позиции, 2-3 предложения"
            }},
            "authenticity_analysis": {{
                "linguistic_patterns": "анализ лингвистических паттернов, указывающих на авторство (человек/ИИ)",
                "specificity_score": "оценка конкретности и детализации ответов, от 0 до 100",
                "personal_experience_indicators": "наличие индикаторов личного опыта в ответах, от 0 до 10",
                "ai_probability_breakdown": {{
                    "template_phrases": число от 0 до 100,
                    "perfect_structure": число от 0 до 100,
                    "lack_of_specifics": число от 0 до 100,
                    "repetitive_patterns": число от 0 до 100
                }},
                "overall_authenticity_score": число от 0 до 100
            }},
            "requirements_match_matrix": [
                {{
                    "requirement": "требование из вакансии",
                    "match_level": "полное/частичное/отсутствует",
                    "evidence": "доказательства соответствия из резюме или ответов",
                    "gap_analysis": "анализ разрыва между требованием и квалификацией кандидата",
                    "weight": число от 1 до 10,
                    "weighted_score": число от 0 до 100
                }},
                // дополнительные требования
            ],
            "market_context": {{
                "candidate_rarity": "оценка редкости навыков кандидата на рынке труда, от 1 до 10",
                "competition_adjustment": "корректирующий коэффициент для match_percent на основе рыночной конкуренции, от 0.9 до 1.1",
                "market_analysis": "краткий анализ рыночной позиции кандидата, не менее 2-3 предложений"
            }},
            "match_calculation": {{
                "base_weighted_score": "рассчитывается как сумма(score * weight) для каждого критерия, деленная на сумму весов",
                "quality_adjustment": "корректировка на основе полноты и согласованности данных",
                "market_adjustment": "корректировка на основе рыночных факторов",
                "requirements_alignment": "расчёт на основе requirements_match_matrix",
                "stop_factors_penalty": "штрафные баллы на основе стоп-факторов",
                "final_match_percent": "итоговый процент соответствия после всех корректировок"
            }},
            "data_request": {{
                "priority_requests": ["список наиболее критичных отсутствующих данных"],
                "secondary_requests": ["список желательных дополнительных данных"],
                "clarification_requests": ["список вопросов для прояснения неоднозначностей"],
                "request_urgency": число от 1 до 5,
                "expected_impact_on_assessment": "описание того, как получение запрашиваемых данных повлияет на оценку, 2-3 предложения"
            }},
            "additional_data_requests": {{
                "critical_missing_data": [
                    {{
                        "field": "название отсутствующего поля",
                        "importance": "критическая/высокая/средняя/низкая",
                        "impact_on_assessment": "как отсутствие влияет на оценку",
                        "specific_request": "конкретный запрос информации в форме вопроса",
                        "alternatives": "альтернативные источники или формы этой информации"
                    }},
                    // дополнительные отсутствующие поля
                ],
                "request_template": "готовый шаблон письма для запроса дополнительной информации у кандидата",
                "prioritized_questions": ["список приоритетных вопросов в порядке важности"]
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
        5. 5 профессиональных вопросов для кандидата
        6. 5 вопросов на soft skills
        
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
                
            # Добавляем метаданные о генерации
            from datetime import datetime
            vacancy_data.update({
                'is_ai_generated': True,
                'ai_generation_date': datetime.now().isoformat(),
                'ai_generation_promt': prompt,
                'ai_generation_metadata': {
                    'model': 'gpt-4o',
                    'temperature': 0.7,
                    'max_tokens': 4000,
                    'generation_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            })
                
        except json.JSONDecodeError:
            current_app.logger.error(f"Не удалось распарсить JSON из ответа API: {result[:500]}")
            return None
        
        # Логируем успешную генерацию
        current_app.logger.info(f"Успешно сгенерирована вакансия с помощью AI: {vacancy_data['title']}")
        
        return vacancy_data
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при генерации вакансии с помощью AI: {str(e)}")
        return None 