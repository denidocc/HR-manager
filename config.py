import os
from datetime import timedelta
from dotenv import load_dotenv

# Принудительно перезагружаем переменные окружения
load_dotenv(override=True)

# Функция для безопасного получения переменных окружения
def get_env_variable(name, default=None, required=False):
    """
    Безопасно получает переменную окружения с проверкой на заглушки
    
    Args:
        name: Имя переменной окружения
        default: Значение по умолчанию, если переменная не найдена
        required: Если True, вызывает исключение при отсутствии переменной
        
    Returns:
        Значение переменной окружения или значение по умолчанию
    """
    value = os.environ.get(name, default)
    
    # Проверка на заглушки (только для определенных переменных)
    if name in ['OPENAI_API_KEY', 'SECRET_KEY', 'JWT_SECRET_KEY', 'ENCRYPTION_KEY']:
        if value and ('your-' in value or 'replace-' in value):
            # Логирование предупреждения
            print(f"ВНИМАНИЕ: Переменная {name} содержит заглушку: {value[:10]}...")
            if required:
                raise ValueError(f"Требуется реальное значение для {name}. Текущее значение содержит заглушку.")
            return default
    
    # Проверка наличия значения для обязательных переменных
    if required and not value:
        raise ValueError(f"Не найдена обязательная переменная окружения: {name}")
        
    return value

class Config:
    # Основные настройки Flask
    SECRET_KEY = get_env_variable('SECRET_KEY', 'dev-secret-key-replace-in-production')
    DEBUG = get_env_variable('FLASK_DEBUG', 'True') == 'True'
    
    # Настройки базы данных
    DB_USER = get_env_variable('DB_USER', 'postgres')
    DB_PASSWORD = get_env_variable('DB_PASSWORD', 'postgres')
    DB_HOST = get_env_variable('DB_HOST', 'localhost')
    DB_PORT = get_env_variable('DB_PORT', '5432')
    DB_NAME = get_env_variable('DB_NAME', 'hr_manager')
    
    SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки шифрования для PostgreSQL pgp_sym_encrypt
    ENCRYPTION_KEY = get_env_variable('ENCRYPTION_KEY', 'pgp-encryption-key-replace-in-production')
    ENCRYPTION_OPTIONS = get_env_variable('ENCRYPTION_OPTIONS', 'cipher-algo=aes256')
    
    # JWT настройки
    JWT_SECRET_KEY = get_env_variable('JWT_SECRET_KEY', 'jwt-secret-key-replace-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=15)
    
    # Настройки загрузки файлов
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'jpg', 'jpeg', 'png'}
    
    # Email настройки
    MAIL_SERVER = get_env_variable('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(get_env_variable('MAIL_PORT', 587))
    MAIL_USE_TLS = get_env_variable('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = get_env_variable('MAIL_USERNAME')
    MAIL_PASSWORD = get_env_variable('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = get_env_variable('MAIL_DEFAULT_SENDER', 'noreply@hrmanager.com')
    
    # OpenAI API - обязательный ключ без заглушек
    OPENAI_API_KEY = get_env_variable('OPENAI_API_KEY', required=False)
    
    # Проверяем наличие OpenAI API ключа на старте
    if not OPENAI_API_KEY or "your-" in OPENAI_API_KEY or len(OPENAI_API_KEY) < 20:
        print("ПРЕДУПРЕЖДЕНИЕ: OpenAI API ключ отсутствует или некорректен. Функции AI будут недоступны.")
    
    # Настройки Redis для фоновых задач
    REDIS_URL = get_env_variable('REDIS_URL', 'redis://localhost:6379/0')
    
    # Настройки логирования
    LOG_LEVEL = get_env_variable('LOG_LEVEL', 'INFO')
    LOG_FILENAME = get_env_variable('LOG_FILENAME', 'app.log')

    # Настройки логирования
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'level': 'INFO'
            }
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': True
            },
            'sqlalchemy.engine': {
                'handlers': [],
                'level': 'WARNING',
                'propagate': False
            }
        }
    }
    
    # Настройки кэширования
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Настройки сессии
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # Включенные функции
    ENABLED_FEATURES = ['ai_analysis']

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