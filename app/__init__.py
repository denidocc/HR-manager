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

# Инициализация расширений
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
jwt = JWTManager()
mail = Mail()
argon2 = Argon2()
csrf = CSRFProtect()
cache = Cache()

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
    
    # Настройка логирования
    logging.config.dictConfig(app.config['LOGGING_CONFIG'])
    
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
    # Формат логов
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    
    # Настройка логгера Flask
    app.logger.handlers.clear()
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(console_handler)
    
    # Отключаем логи от werkzeug ниже WARNING
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)
    
    # Отключаем логи от SQLAlchemy ниже WARNING
    sa_logger = logging.getLogger('sqlalchemy')
    sa_logger.setLevel(logging.WARNING)
    
    # Отключаем логи от PostgreSQL
    logging.getLogger('psycopg2').setLevel(logging.WARNING)
    logging.getLogger('psycopg2.pool').setLevel(logging.WARNING)
    
    return app