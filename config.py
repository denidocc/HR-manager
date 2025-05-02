import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Основные настройки Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-replace-in-production')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True') == 'True'
    
    # Настройки базы данных
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'hr_manager')
    
    SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT настройки
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-replace-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=15)
    
    # Настройки загрузки файлов
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'jpg', 'jpeg', 'png'}
    
    # Email настройки
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@hrmanager.com')
    
    # OpenAI API
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    
    # Настройки Redis для фоновых задач
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Настройки логирования
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILENAME = os.environ.get('LOG_FILENAME', 'app.log')

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 