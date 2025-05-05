#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, jsonify, request, flash, session, make_response, send_file, send_from_directory, abort
from app.controllers.auth import auth_bp
from app.controllers.dashboard import dashboard_bp
from app.controllers.vacancies import vacancies_bp
from app.controllers.candidates import candidates_bp
from app.controllers.files import files_bp
from app.controllers.ai_analysis import ai_analysis_bp
from app.controllers.public import public_bp
from app.controllers.index import index_bp

# Список всех blueprints
blueprints = [
    index_bp,
    auth_bp,
    dashboard_bp,
    vacancies_bp,
    candidates_bp,
    files_bp,
    ai_analysis_bp,
    public_bp
]

def register_blueprints(app):
    """Регистрация всех blueprints в приложении"""
    for blueprint in blueprints:
        app.register_blueprint(blueprint)
    
    # Регистрация обработчиков ошибок
    register_error_handlers(app)

def register_error_handlers(app):
    """Регистрация обработчиков ошибок"""
    
    @app.errorhandler(404)
    def handle_404(error):
        """Обработчик ошибки 404: Страница не найдена"""
        return render_template('errors/404.html', title='Страница не найдена'), 404
    
    @app.errorhandler(403)
    def handle_403(error):
        """Обработчик ошибки 403: Доступ запрещен"""
        return render_template('errors/403.html', title='Доступ запрещен'), 403
    
    @app.errorhandler(500)
    def handle_500(error):
        """Обработчик ошибки 500: Внутренняя ошибка сервера"""
        return render_template('errors/500.html', title='Ошибка сервера'), 500