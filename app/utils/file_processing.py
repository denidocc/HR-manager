#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from werkzeug.utils import secure_filename
from flask import current_app
import uuid

# Поддерживаемые расширения файлов
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}

def allowed_file(filename):
    """Проверка допустимости расширения файла"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_resume(file, tracking_code):
    """Сохранение файла резюме"""
    if not file or not allowed_file(file.filename):
        return None
    
    # Получаем расширение файла
    filename = secure_filename(file.filename)
    
    # Проверяем наличие расширения
    parts = filename.rsplit('.', 1) if '.' in filename else [filename, '']
    if len(parts) < 2 or not parts[1]:
        # Если расширение отсутствует или пустое, используем расширение по умолчанию
        extension = 'pdf'  # Расширение по умолчанию
    else:
        extension = parts[1].lower()
    
    # Создаем имя файла на основе кода отслеживания
    new_filename = f"resume_{tracking_code}.{extension}"
    
    # Определяем путь для сохранения
    upload_folder = current_app.config['UPLOAD_FOLDER']
    
    # Создаем директорию, если она не существует
    os.makedirs(upload_folder, exist_ok=True)
    
    # Путь к файлу
    file_path = os.path.join(upload_folder, new_filename)
    
    # Сохраняем файл
    file.save(file_path)
    
    return file_path

def extract_text_from_resume(file_path):
    """Извлечение текста из файла резюме"""
    if not file_path or not os.path.exists(file_path):
        return None
    
    # Проверяем наличие расширения
    parts = file_path.rsplit('.', 1) if '.' in file_path else [file_path, '']
    if len(parts) < 2 or not parts[1]:
        # Если расширение отсутствует или пустое, используем расширение по умолчанию
        extension = 'pdf'  # Расширение по умолчанию
    else:
        extension = parts[1].lower()
    
    # Извлечение текста из разных форматов файлов
    if extension == 'pdf':
        return extract_text_from_pdf(file_path)
    elif extension in ['doc', 'docx']:
        return extract_text_from_docx(file_path)
    elif extension in ['jpg', 'jpeg', 'png']:
        return extract_text_from_image(file_path)
    
    return None

def extract_text_from_pdf(file_path):
    """Извлечение текста из PDF-файла"""
    try:
        import fitz  # PyMuPDF
        
        text = ""
        with fitz.open(file_path) as pdf:
            for page in pdf:
                text += page.get_text()
        
        return text
    except ImportError:
        current_app.logger.error("PyMuPDF (fitz) не установлен. Установите: pip install pymupdf")
        return "Извлечение текста из PDF недоступно. Установите необходимые библиотеки."
    except Exception as e:
        current_app.logger.error(f"Ошибка при извлечении текста из PDF: {str(e)}")
        return None

def extract_text_from_docx(file_path):
    """Извлечение текста из DOCX/DOC файла"""
    try:
        import docx
        
        if file_path.endswith('.docx'):
            doc = docx.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text
        else:
            # Для DOC-файлов может потребоваться дополнительная обработка
            return "Извлечение текста из DOC-файлов в данный момент не поддерживается"
    except ImportError:
        current_app.logger.error("python-docx не установлен. Установите: pip install python-docx")
        return "Извлечение текста из DOCX недоступно. Установите необходимые библиотеки."
    except Exception as e:
        current_app.logger.error(f"Ошибка при извлечении текста из DOCX: {str(e)}")
        return None

def extract_text_from_image(file_path):
    """Извлечение текста из изображения (OCR) - временно отключено"""
    current_app.logger.info(f"Получен запрос на извлечение текста из изображения: {file_path}")
    current_app.logger.info("Функция извлечения текста из изображений временно отключена")
    
    # Возвращаем стандартный текст, указывая, что это изображение
    return "Это изображение. Извлечение текста из изображений временно отключено. Оригинальный файл сохранен и доступен для скачивания." 