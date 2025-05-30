# Правила структурирования проекта Flask с PostgreSQL

# Название проекта: Clever HR

## 1. Структура файлов и каталогов

- **Корневой каталог**:
  - `app/` - основной пакет приложения
  - `migrations/` - миграции базы данных (Alembic)
  - `config.py` - файл конфигурации
  - `.env` - переменные окружения (не включать в репозиторий)
  - `.env.example` - пример файла для настройки
  - `requirements.txt` - зависимости проекта
  - `.flaskenv` - переменные Flask
  - `gunicorn_start.py` - скрипт для запуска с Gunicorn

- **Основной пакет приложения (app/)**:
  - `__init__.py` - инициализация и настройка приложения
  - `models/` - модели данных
  - `controllers/` - контроллеры для веб-интерфейса
  - `mobile_controllers/` - контроллеры для мобильного API
  - `forms/` - формы WTForms
  - `utils/` - вспомогательные функции
  - `static/` - статические файлы
  - `templates/` - шаблоны
  - `version.py` - версионирование приложения
  - `errors.py` - обработка ошибок

## 2. Инициализация приложения

- **Расширения Flask** в `app/__init__.py`:
  - Инициализация основных расширений: SQLAlchemy, Migrate, CSRF, Login, JWT
  - Подключение дополнительных сервисов: Redis, Firebase, APScheduler
  - Настройка логирования с различными обработчиками для консоли и файлов
  - Регистрация всех blueprints
  - Определение обработчиков ошибок и middleware

- **Пример инициализации**:
  ```python
  app = Flask(__name__)
  app.config.from_object(Config)
  app.secret_key = os.environ.get('SECRET_KEY')
  db = SQLAlchemy(app)
  migrate = Migrate(app, db)
  csrf = CSRFProtect(app)
  login = LoginManager(app)
  jwt = JWTManager(app)
  ```

## 3. Правила именования

### Модели
- Имена классов моделей: **CamelCase**
  - Таблицы-справочники (словари): начинаются с `C_` (например, `C_Gender`, `C_User_Status`)
  - Ассоциативные таблицы: используют названия связываемых таблиц с подчеркиванием (например, `User_Roles`)
  - Основные сущности: просто CamelCase (например, `User`, `Booking`)

- Имена файлов моделей: **snake_case**
  - Соответствуют имени класса в snake_case (например, `user.py`, `c_gender.py`)
  - Все модели импортируются в `models/__init__.py`

- Определение таблиц:
  - Использовать параметр `__tablename__` в snake_case (`__tablename__ = 'user'`)
  - Имя таблицы должно соответствовать имени класса в snake_case

### Контроллеры

- Файлы контроллеров:
  - Web: `controllers/имя_функционала.py` (например, `auth.py`, `admin.py`)
  - Mobile: `mobile_controllers/mobile_имя_функционала.py` (например, `mobile_auth.py`)

- Blueprints:
  - Web: `имя_функционала_bp` (например, `auth_bp`, `admin_bp`)
  - Mobile: `mobile_имя_функционала_bp` (например, `mobile_auth_bp`)

- Маршруты:
  - Web: `/имя_функционала/действие` (например, `/auth/login`, `/admin/users`)
  - Mobile: `/app/тип_пользователя/действие` (например, `/app/client/register`, `/app/master/profile`)

- Функции обработчики:
  - Web: `имя_действия` (например, `login`, `admin_index`)
  - Mobile: `app_тип_пользователя_действие` (например, `app_client_register`)

### Утилиты

- Классы утилит:
  - CamelCase с говорящим названием (например, `PushNotificationService`)
  - Сгруппированные методы для одной сущности

- Файлы утилит:
  - snake_case (`api_response.py`, `push_notif_service.py`)
  - Каждая утилита в отдельном файле

- Константы:
  - UPPER_CASE с подчеркиваниями
  - Определять на уровне класса или модуля

## 4. Модели и типизация данных

- **Обязательное использование типизации**:
  ```python
  id: so.Mapped[int] = so.mapped_column(primary_key=True)
  name: so.Mapped[str] = so.mapped_column(sa.Text, index=True)
  is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
  created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True))
  ```

- **Текстовые поля**:
  - Всегда использовать `sa.Text` для строковых полей, а не `String`
  - Использовать `index=True` для полей, по которым будет поиск

- **Отношения**:
  - Аннотировать тип с указанием класса в кавычках
  ```python
  user: so.Mapped["User"] = so.relationship(back_populates="tokens")
  services: so.Mapped[list["Service"]] = so.relationship(back_populates="user")
  ```

- **Шифрование чувствительных данных**:
  - Использовать PostgreSQL pgp_sym_encrypt для шифрования
  - Имена зашифрованных полей начинаются с подчеркивания (`_phone`, `_email`)
  - Создавать свойства для доступа к расшифрованным данным

## 5. Конфигурация

- Использовать класс `Config` в `config.py`
- Загружать конфигурацию из `.env` файла
- Разделять конфигурацию на секции:
  - Основные настройки Flask
  - Настройки базы данных
  - Секреты и токены
  - Настройки API и внешних сервисов
  - Пути к файлам и папкам

- **Пример конфигурации**:
  ```python
  class Config:
      SECRET_KEY = os.environ.get('SECRET_KEY')
      DB_NAME = os.environ.get('DB_NAME')
      DB_USER = os.environ.get('DB_USER')
      SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
      JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
      JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=15)
  ```

## 6. Аутентификация и авторизация

- JWT для API
- Сессии для веб-интерфейса
- Запрет CSRF для API, включение для веб-интерфейса
- Хранить токены в базе данных и отслеживать отозванные токены

- **Декораторы аутентификации**:
  ```python
  @auth_required
  @safe_jwt_required()
  @admin_required
  ```

- **Типовой механизм проверки**:
  ```python
  def auth_required(f):
      @wraps(f)
      def decorated(*args, **kwargs):
          if not current_user.is_authenticated:
              try:
                  verify_jwt_in_request()
              except:
                  abort(401)
          return f(*args, **kwargs)
      return decorated
  ```

## 7. Обработка данных

- **Валидация входных данных**:
  - Проверка обязательных полей
  - Валидация форматов (телефоны, email)
  - Проверка бизнес-правил

- **Шифрование чувствительных данных**:
  - Использовать PostgreSQL pgp_sym_encrypt
  - Хранить закрытые ключи отдельно от кода

- **Работа с транзакциями**:
  ```python
  try:
      # операции с БД
      db.session.commit()
  except:
      db.session.rollback()
      raise
  ```

## 8. API принципы

- **Единый формат ответов**:
  ```python
  def api_response(status="success", message="", data=None, status_code=200, ...):
      response = {"status": status, "message": message, "data": data}
      return jsonify(response), status_code
  ```

- **Стандартизированная обработка ошибок**:
  ```python
  class APIErrors:
      USER_NOT_FOUND = APIError(code="user_not_found", message="User not found", status_code=404)
      
      @staticmethod
      def to_response(error):
          return {"status": "error", "message": error.message, "error_code": error.code, "status_code": error.status_code}
  ```

- **Документация Swagger**:
  - Описание всех эндпоинтов
  - Примеры запросов и ответов
  - Схемы данных

## 9. Логирование

- **Настройка логгеров**:
  - Файловый и консольный логгеры
  - Различные уровни для разных сред (development, production)
  - Структурированный формат логов

- **Стандартное использование**:
  ```python
  app.logger.info("Starting process...")
  app.logger.warning("Warning condition")
  app.logger.error("Error occurred", exc_info=True)
  ```

- **Контекстная информация**:
  ```python
  app.logger.error("Error", extra={"user_id": user_id, "request_data": data})
  ```

## 10. Разделение мобильного и веб-интерфейса

- Отдельные контроллеры для веб и мобильного API
- Различные префиксы URL для разных типов клиентов
- Специфические декораторы для мобильных эндпоинтов

- **Web контроллеры**:
  - Возвращают HTML шаблоны
  - Используют Flash сообщения
  - Работают с сессиями

- **Mobile контроллеры**:
  - Возвращают только JSON
  - Используют JWT аутентификацию
  - Имеют более детальную обработку ошибок

## 11. Безопасность

- **Хеширование паролей**:
  - Использовать Argon2 (более современный и безопасный)
  - Отслеживать изменения паролей

- **Шифрование чувствительных данных**:
  - Телефоны, email и другие персональные данные

- **Защита от атак**:
  - CSRF защита для веб-форм
  - Ограничение скорости запросов (rate limiting)
  - Проверка API ключей
  - Безопасные заголовки HTTP

- **Проверка входных данных**:
  - Валидация всех данных от пользователя
  - Предотвращение SQL инъекций через ORM
  - Экранирование HTML при выводе


## 12. Стилистика написания кода

- **DRY**
- **Clean Code**
- **Не писать код стилей в теге head**
- **Прежде чем начать создавать что-то новое пересмотри структуру проекта**
- **use context7**
- **Сначало распиши что ты понял от ответа пользователя и задай уточняющие вопросы а после ответа от пользователя начинай генерировать код**