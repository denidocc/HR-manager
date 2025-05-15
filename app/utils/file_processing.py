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
    """Извлечение данных из файла резюме с использованием AI-сервиса"""
    current_app.logger.info(f"Начало извлечения данных из файла: {file_path}")
    
    if not file_path or not os.path.exists(file_path):
        current_app.logger.error(f"Файл не существует или путь не указан: {file_path}")
        return None
    
    try:
        # Используем функцию extract_resume_text из ai_service.py
        from app.utils.ai_service import extract_resume_text
        extracted_data = extract_resume_text(file_path)
        
        if not extracted_data:
            current_app.logger.error(f"Не удалось извлечь данные из файла: {file_path}")
            return None
            
        current_app.logger.info(f"Успешно извлечены данные из файла: {file_path}")
        return extracted_data
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при извлечении данных из файла: {str(e)}", exc_info=True)
        return None