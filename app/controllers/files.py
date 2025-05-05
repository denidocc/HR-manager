#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, request, jsonify, send_from_directory, current_app, abort
from flask_login import login_required, current_user
from app.models import SystemLog
from werkzeug.utils import secure_filename
import os
import uuid

files_bp = Blueprint('files', __name__, url_prefix='/files')

@files_bp.route('/upload', methods=['POST'])
def upload_file():
    """API для загрузки файлов"""
    # Проверяем, есть ли файл в запросе
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Нет файла в запросе'}), 400
    
    file = request.files['file']
    
    # Проверяем, выбран ли файл
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'Файл не выбран'}), 400
    
    # Проверяем расширение файла
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'})
    if not file.filename.lower().endswith(tuple('.' + ext for ext in allowed_extensions)):
        return jsonify({'status': 'error', 'message': f'Недопустимый формат файла. Разрешены только: {", ".join(allowed_extensions)}'}), 400
    
    # Проверяем размер файла
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024)  # По умолчанию 10 МБ
    if request.content_length > max_size:
        return jsonify({'status': 'error', 'message': f'Размер файла превышает максимально допустимый ({max_size // (1024 * 1024)} МБ)'}), 400
    
    # Генерируем уникальное имя файла
    filename = secure_filename(file.filename)
    unique_id = str(uuid.uuid4())
    extension = filename.rsplit('.', 1)[1].lower()
    new_filename = f"{unique_id}.{extension}"
    
    # Определяем путь для сохранения
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, new_filename)
    
    # Создаем директорию, если она не существует
    os.makedirs(upload_folder, exist_ok=True)
    
    # Сохраняем файл
    file.save(file_path)
    
    # Логируем загрузку файла
    user_id = current_user.id if current_user.is_authenticated else None
    SystemLog.log(
        event_type="file_upload",
        description=f"Загружен файл: {filename} (сохранен как {new_filename})",
        user_id=user_id,
        ip_address=request.remote_addr
    )
    
    return jsonify({
        'status': 'success',
        'message': 'Файл успешно загружен',
        'filename': new_filename,
        'original_name': filename
    }), 200

@files_bp.route('/<filename>')
def download_file(filename):
    """Загрузка файла"""
    # Для безопасности проверяем, что filename не содержит путей
    if '/' in filename or '\\' in filename:
        abort(404)
    
    upload_folder = current_app.config['UPLOAD_FOLDER']
    
    # Проверяем, существует ли файл
    if not os.path.exists(os.path.join(upload_folder, filename)):
        abort(404)
    
    # Логируем загрузку файла
    user_id = current_user.id if current_user.is_authenticated else None
    SystemLog.log(
        event_type="file_download",
        description=f"Скачан файл: {filename}",
        user_id=user_id,
        ip_address=request.remote_addr
    )
    
    return send_from_directory(upload_folder, filename, as_attachment=True)

@files_bp.route('/view/<filename>')
def view_file(filename):
    """Просмотр файла (без скачивания)"""
    # Для безопасности проверяем, что filename не содержит путей
    if '/' in filename or '\\' in filename:
        abort(404)
    
    upload_folder = current_app.config['UPLOAD_FOLDER']
    
    # Проверяем, существует ли файл
    if not os.path.exists(os.path.join(upload_folder, filename)):
        abort(404)
    
    # Логируем просмотр файла
    user_id = current_user.id if current_user.is_authenticated else None
    SystemLog.log(
        event_type="file_view",
        description=f"Просмотрен файл: {filename}",
        user_id=user_id,
        ip_address=request.remote_addr
    )
    
    return send_from_directory(upload_folder, filename, as_attachment=False)

@files_bp.route('/delete/<filename>', methods=['POST'])
@login_required
def delete_file(filename):
    """Удаление файла"""
    # Для безопасности проверяем, что filename не содержит путей
    if '/' in filename or '\\' in filename:
        abort(404)
    
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, filename)
    
    # Проверяем, существует ли файл
    if not os.path.exists(file_path):
        return jsonify({'status': 'error', 'message': 'Файл не найден'}), 404
    
    # Удаляем файл
    os.remove(file_path)
    
    # Логируем удаление файла
    SystemLog.log(
        event_type="file_delete",
        description=f"Удален файл: {filename}",
        user_id=current_user.id,
        ip_address=request.remote_addr
    )
    
    return jsonify({'status': 'success', 'message': 'Файл успешно удален'}), 200 