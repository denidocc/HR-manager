# HR-manager

## Описание проекта

HR-manager - это современная система управления персоналом, разработанная на Flask с использованием PostgreSQL. Система предоставляет полный набор инструментов для управления вакансиями, кандидатами, собеседованиями и процессами найма.

## Основные возможности

- Управление вакансиями с поддержкой AI-генерации описаний
- Система откликов на вакансии с автоматическим анализом резюме
- Канбан-доска для отслеживания кандидатов
- Автоматическое распознавание и анализ резюме
- Система проведения собеседований
- Интеграция с внешними сервисами
- Мобильное API для работы с системой

## Технический стек

- **Backend**: Python 3.12, Flask
- **База данных**: PostgreSQL
- **ORM**: SQLAlchemy
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **AI/ML**: OpenAI API для генерации контента
- **OCR**: Tesseract для распознавания текста
- **Аутентификация**: JWT + сессии

## Требования к системе

- Python 3.12+
- PostgreSQL 15+
- Tesseract OCR
- Node.js 18+ (для сборки фронтенда)

## Установка и настройка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/denidocc/HR-manager.git
cd HR-manager
```

2. Создайте и активируйте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/macOS
# или
.\venv\Scripts\activate  # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

5. Настройте переменные окружения в `.env`:
```env
FLASK_APP=app
FLASK_ENV=development
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:password@localhost:5432/hr_manager
OPENAI_API_KEY=your-openai-api-key
```

6. Инициализируйте базу данных:
```bash
flask db upgrade
```

7. Создайте первого администратора:
```bash
flask create-admin
```

## Конфигурация

Проект использует систему конфигурации на основе классов:

- `Config` - базовый класс с общими настройками
- `DevelopmentConfig` - настройки для разработки (включен режим отладки и логирование SQL)
- `TestingConfig` - настройки для тестирования (использует SQLite в памяти)
- `ProductionConfig` - продакшн настройки (отключена отладка и тестирование)

Конфигурация выбирается через переменную окружения `FLASK_ENV`:
```bash
FLASK_ENV=development  # для разработки
FLASK_ENV=production   # для продакшена
FLASK_ENV=testing     # для тестов
```

Основные настройки в `.env`:
```env
FLASK_APP=app
FLASK_ENV=development
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:password@localhost:5432/hr_manager
OPENAI_API_KEY=your-openai-api-key
```

## Запуск проекта

### Разработка

1. Запустите сервер разработки:
```bash
flask run
```

2. Откройте http://localhost:5000 в браузере

### Продакшн

1. Настройте Gunicorn:
```bash
gunicorn -c gunicorn_config.py "app:create_app()"
```

## Структура проекта

```
HR-manager/
├── app/
│   ├── __init__.py
│   ├── models/
│   ├── controllers/
│   ├── mobile_controllers/
│   ├── forms/
│   ├── utils/
│   ├── static/
│   └── templates/
├── migrations/
├── tests/
├── config.py
├── requirements.txt
└── README.md
```

## Развертывание

1. Настройте сервер:
```bash
sudo apt update
sudo apt install python3-venv postgresql nginx
```

2. Создайте базу данных:
```sql
CREATE DATABASE hr_manager;
CREATE USER hr_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE hr_manager TO hr_user;
```

3. Настройте Nginx:
```bash
sudo cp nginx/hr_manager.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/hr_manager.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

4. Настройте systemd:
```bash
sudo cp systemd/hr_manager.service /etc/systemd/system/
sudo systemctl enable hr_manager
sudo systemctl start hr_manager
```

## Безопасность

- Все пароли хешируются с использованием Argon2
- Чувствительные данные шифруются в базе данных
- CSRF защита для веб-форм
- Rate limiting для API
- JWT для мобильного API
- Сессии для веб-интерфейса

## Поддержка

При возникновении проблем:
1. Проверьте логи в `logs/`
2. Создайте issue в репозитории
3. Обратитесь к документации в `/docs`

## Лицензия

MIT License