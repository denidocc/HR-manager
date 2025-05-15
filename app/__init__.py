import os
import logging
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_argon2 import Argon2
from flask_wtf.csrf import CSRFProtect
from config import config
from logging.handlers import RotatingFileHandler
from flask_caching import Cache
import logging.config
import re
from markupsafe import Markup

# Отключаем логирование SQLAlchemy на уровне модуля
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)

# Инициализация расширений
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
jwt = JWTManager()
mail = Mail()
argon2 = Argon2()
csrf = CSRFProtect()
cache = Cache()

# Функция для преобразования переносов строк в HTML-теги br
def nl2br(value):
    if value:
        value = re.sub(r'\r\n|\r|\n', '<br>', value)
        return Markup(value)
    return ''

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    argon2.init_app(app)
    csrf.init_app(app)
    cache.init_app(app)
    
    # Регистрация пользовательских фильтров Jinja2
    app.jinja_env.filters['nl2br'] = nl2br
    
    # Создание директории для загрузки файлов, если её нет
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    # Регистрация Blueprint'ов
    from app.controllers import register_blueprints
    register_blueprints(app)
    
    # Настройка login_manager
    login_manager.login_view = 'auth_bp.login'
    login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))
    
    # Добавим настройку логирования
    setup_logging(app)
    
    return app

# Настройка логирования
def setup_logging(app):
    # Удаляем все существующие обработчики из корневого логгера
    # чтобы избежать дублирования логов
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    # Формат логов
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Настройка корневого логгера
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    
    # Очищаем обработчики логгера Flask
    app.logger.handlers.clear()
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False  # Отключаем распространение логов в родительский логгер
    app.logger.addHandler(console_handler)
    
    # Отключаем логи от werkzeug ниже WARNING
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)
    werkzeug_logger.propagate = False  # Отключаем распространение логов
    
    # Отключаем логи от SQLAlchemy ниже WARNING
    sa_logger = logging.getLogger('sqlalchemy')
    sa_logger.setLevel(logging.ERROR)  # Повышаем уровень до ERROR
    sa_logger.propagate = False  # Отключаем распространение логов
    
    # Полностью отключаем логи от SQLAlchemy Engine
    sa_engine_logger = logging.getLogger('sqlalchemy.engine')
    sa_engine_logger.setLevel(logging.ERROR)  # Устанавливаем уровень ERROR
    sa_engine_logger.propagate = False  # Отключаем распространение логов
    
    # Отключаем логи от PostgreSQL
    psycopg2_logger = logging.getLogger('psycopg2')
    psycopg2_logger.setLevel(logging.WARNING)
    psycopg2_logger.propagate = False  # Отключаем распространение логов
    
    psycopg2_pool_logger = logging.getLogger('psycopg2.pool')
    psycopg2_pool_logger.setLevel(logging.WARNING)
    psycopg2_pool_logger.propagate = False  # Отключаем распространение логов
    
    # Настройка логгеров для наших модулей
    for logger_name in ['app.utils.image_processor', 'app.utils.handwriting_recognizer', 'app.utils.form_analyzer']:
        module_logger = logging.getLogger(logger_name)
        module_logger.handlers.clear()
        module_logger.setLevel(logging.INFO)
        module_logger.propagate = False  # Отключаем распространение логов
        module_logger.addHandler(console_handler)
    
    return app