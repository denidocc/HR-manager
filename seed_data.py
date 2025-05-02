#!/usr/bin/env python
# -*- coding: utf-8 -*-
import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from faker import Faker
from app import create_app, db
from app.models import User, Vacancy, Candidate, Notification, SystemLog
from app.models import C_Gender, C_User_Status, C_Candidate_Status, C_Employment_Type
from tqdm import tqdm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from flask_jwt_extended import create_access_token, create_refresh_token

# Инициализация Faker с русской локализацией
fake = Faker('ru_RU')

def create_if_not_exists(model, name, id=None, **kwargs):
    """Создает запись в справочнике, если она не существует"""
    if not model.query.filter_by(name=name).first():
        new_entry = model(name=name, **kwargs)
        if id is not None:
            new_entry.id = id
        db.session.add(new_entry)
        return new_entry
    return model.query.filter_by(name=name).first()

def create_c_gender():
    """Создание справочника полов"""
    genders = [
        {'name': 'Не указан', 'short_name': 'Н/У'},
        {'name': 'Мужской', 'short_name': 'М'},
        {'name': 'Женский', 'short_name': 'Ж'}
    ]
    for i, gender in enumerate(genders):
        create_if_not_exists(C_Gender, gender['name'], i, short_name=gender['short_name'])
    db.session.commit()
    print("Справочник полов успешно создан")

def create_c_user_status():
    """Создание справочника статусов пользователей"""
    statuses = ['Неизвестно', 'Активный', 'Неактивный', 'Заблокирован', 'Удален']
    for i, status in enumerate(statuses):
        create_if_not_exists(C_User_Status, status, i)
    db.session.commit()
    print("Справочник статусов пользователей успешно создан")

def create_c_candidate_status():
    """Создание справочника статусов кандидатов"""
    statuses = [
        {'name': 'Новый', 'description': 'Кандидат только что подал заявку', 'color_code': '#3498db'},
        {'name': 'Назначено интервью', 'description': 'Кандидату назначено собеседование', 'color_code': '#f39c12'},
        {'name': 'Отклонен', 'description': 'Кандидат не прошел отбор', 'color_code': '#e74c3c'},
        {'name': 'Принят', 'description': 'Кандидат принят на работу', 'color_code': '#2ecc71'},
        {'name': 'Ожидает решения', 'description': 'Кандидат ожидает решения после интервью', 'color_code': '#9b59b6'}
    ]
    for i, status in enumerate(statuses):
        existing = C_Candidate_Status.query.filter_by(name=status['name']).first()
        if not existing:
            new_status = C_Candidate_Status(
                id=i,
                name=status['name'],
                description=status['description'],
                color_code=status['color_code']
            )
            db.session.add(new_status)
    db.session.commit()
    print("Справочник статусов кандидатов успешно создан")

def create_c_employment_type():
    """Создание справочника типов занятости"""
    employment_types = [
        {'name': 'Полный день', 'description': 'Работа с 9 до 18'},
        {'name': 'Неполный день', 'description': 'Частичная занятость'},
        {'name': 'Удаленно', 'description': 'Работа из дома'},
        {'name': 'Гибкий график', 'description': 'Свободный график работы'},
        {'name': 'Сменный график', 'description': 'Работа по сменам'}
    ]
    for i, emp_type in enumerate(employment_types):
        existing = C_Employment_Type.query.filter_by(name=emp_type['name']).first()
        if not existing:
            new_type = C_Employment_Type(
                id=i,
                name=emp_type['name'],
                description=emp_type['description']
            )
            db.session.add(new_type)
    db.session.commit()
    print("Справочник типов занятости успешно создан")

def create_admin_user():
    """Создание администратора системы"""
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(
            email='admin@hr-manager.com',
            role='admin',
            full_name='Администратор Системы',
            id_c_gender=1,
            id_c_user_status=1,
            is_active=True
        )
        admin.set_password('adminpassword')
        db.session.add(admin)
        db.session.commit()
        print("Администратор успешно создан")
    else:
        print("Администратор уже существует")

def create_hr_users(num_users=5):
    """Создание HR-менеджеров"""
    existing_count = User.query.filter_by(role='hr').count()
    if existing_count >= num_users:
        print(f"Уже существует {existing_count} HR-менеджеров. Пропускаем создание.")
        return

    for _ in tqdm(range(num_users - existing_count), desc="Создание HR-менеджеров"):
        gender_id = random.choice([1, 2])  # Мужской или женский
        first_name = fake.first_name_male() if gender_id == 1 else fake.first_name_female()
        last_name = fake.last_name_male() if gender_id == 1 else fake.last_name_female()
        
        user = User(
            email=fake.email(),
            phone=fake.phone_number(),
            role='hr',
            full_name=f"{first_name} {last_name}",
            id_c_gender=gender_id,
            id_c_user_status=1,  # Активный
            created_at=fake.date_time_between(start_date='-1y', end_date='now', tzinfo=timezone.utc),
            is_active=True
        )
        user.set_password('hr' + fake.password(length=8))
        db.session.add(user)
    
    db.session.commit()
    print(f"Создано {num_users - existing_count} HR-менеджеров")

def create_candidates(num_candidates=20):
    """Создание кандидатов для тестирования"""
    # Сначала проверяем, есть ли вакансии
    vacancies = Vacancy.query.all()
    if not vacancies:
        print("Нет вакансий для кандидатов. Сначала создайте вакансии.")
        return
    
    existing_count = Candidate.query.count()
    if existing_count >= num_candidates:
        print(f"Уже существует {existing_count} кандидатов. Пропускаем создание.")
        return
    
    statuses = C_Candidate_Status.query.all()
    
    for _ in tqdm(range(num_candidates - existing_count), desc="Создание кандидатов"):
        vacancy = random.choice(vacancies)
        
        # Генерируем базовые ответы на вопросы
        base_answers = {
            "location": fake.city(),
            "experience_years": random.randint(0, 10),
            "education": random.choice(["Среднее", "Высшее", "Специальное"]),
            "desired_salary": random.randint(30000, 150000)
        }
        
        # Генерируем ответы на вопросы вакансии
        vacancy_answers = {}
        if vacancy.questions_json:
            for question in vacancy.questions_json:
                vacancy_answers[question['id']] = fake.paragraph()
        
        # Генерируем ответы на софт-скилл вопросы
        soft_answers = {}
        if vacancy.soft_questions_json:
            for question in vacancy.soft_questions_json:
                soft_answers[question['id']] = fake.paragraph()
        
        # Генерируем данные AI-анализа
        ai_match_percent = random.randint(40, 95)
        ai_pros = "\n".join([f"+ {fake.sentence()}" for _ in range(random.randint(2, 5))])
        ai_cons = "\n".join([f"- {fake.sentence()}" for _ in range(random.randint(1, 3))])
        ai_recommendation = random.choice([
            "Рекомендуется к собеседованию",
            "Условно рекомендуется, требуется дополнительная проверка",
            "Не рекомендуется, недостаточно опыта",
            "Высокий приоритет, полное соответствие требованиям"
        ])
        
        # Сгенерируем баллы для разных категорий
        ai_score_location = random.randint(0, 100)
        ai_score_experience = random.randint(0, 100)
        ai_score_tech = random.randint(0, 100)
        ai_score_education = random.randint(0, 100)
        
        # И комментарии к оценкам
        ai_score_comments = {
            "location": fake.paragraph(),
            "experience": fake.paragraph(),
            "tech": fake.paragraph(),
            "education": fake.paragraph()
        }
        
        # Определяем статус кандидата
        status = random.choice(statuses)
        
        # Если статус "Назначено интервью", генерируем дату интервью
        interview_date = None
        if status.name == "Назначено интервью":
            interview_date = fake.date_time_between(start_date='now', end_date='+30d', tzinfo=timezone.utc)
        
        candidate = Candidate(
            vacancy_id=vacancy.id,
            full_name=fake.name(),
            email=fake.email(),
            phone=fake.phone_number(),
            base_answers=base_answers,
            vacancy_answers=vacancy_answers,
            soft_answers=soft_answers,
            resume_path=None,  # В реальности здесь был бы путь к загруженному резюме
            resume_text=fake.text(max_nb_chars=1000),
            ai_match_percent=ai_match_percent,
            ai_pros=ai_pros,
            ai_cons=ai_cons,
            ai_recommendation=ai_recommendation,
            ai_score_location=ai_score_location,
            ai_score_experience=ai_score_experience,
            ai_score_tech=ai_score_tech,
            ai_score_education=ai_score_education,
            ai_score_comments_location=ai_score_comments["location"],
            ai_score_comments_experience=ai_score_comments["experience"],
            ai_score_comments_tech=ai_score_comments["tech"],
            ai_score_comments_education=ai_score_comments["education"],
            id_c_candidate_status=status.id,
            interview_date=interview_date,
            hr_comment=fake.paragraph() if random.choice([True, False]) else None,
            created_at=fake.date_time_between(start_date='-30d', end_date='now', tzinfo=timezone.utc),
            tracking_code=str(uuid.uuid4())
        )
        
        db.session.add(candidate)
    
    db.session.commit()
    print(f"Создано {num_candidates - existing_count} кандидатов")

def create_vacancies(num_vacancies=10):
    """Создание вакансий для тестирования"""
    # Проверяем, есть ли HR-менеджеры
    hrs = User.query.filter_by(role='hr').all()
    if not hrs:
        print("Нет HR-менеджеров для создания вакансий. Сначала создайте HR-менеджеров.")
        return
    
    employment_types = C_Employment_Type.query.all()
    if not employment_types:
        print("Нет типов занятости. Сначала создайте справочник типов занятости.")
        return
    
    existing_count = Vacancy.query.count()
    if existing_count >= num_vacancies:
        print(f"Уже существует {existing_count} вакансий. Пропускаем создание.")
        return
    
    job_titles = [
        "Разработчик Python", "Data Scientist", "Frontend Developer", 
        "DevOps инженер", "QA инженер", "Product Manager", 
        "UX/UI дизайнер", "Backend Developer", "Mobile Developer",
        "Project Manager", "HR Manager", "Marketing Specialist", 
        "Content Manager", "Sales Manager", "Support Specialist",
        "Business Analyst", "System Administrator", "Network Engineer",
        "Database Administrator", "Chief Technology Officer"
    ]
    
    for _ in tqdm(range(num_vacancies - existing_count), desc="Создание вакансий"):
        # Выбираем случайного HR-менеджера
        hr = random.choice(hrs)
        
        # Выбираем случайный тип занятости
        employment_type = random.choice(employment_types)
        
        # Выбираем случайное название вакансии
        title = random.choice(job_titles)
        
        # Генерируем вопросы для вакансии
        questions = []
        for i in range(random.randint(3, 7)):
            questions.append({
                "id": i+1,
                "text": fake.sentence(),
                "type": random.choice(["text", "select", "multiselect"]),
                "options": fake.words(nb=random.randint(3, 6)) if random.choice([True, False]) else None
            })
        
        # Генерируем софт-скилл вопросы
        soft_questions = []
        for i in range(random.randint(2, 5)):
            soft_questions.append({
                "id": i+1,
                "text": fake.sentence(),
                "type": "text"
            })
        
        vacancy = Vacancy(
            title=title,
            id_c_employment_type=employment_type.id,
            description_tasks="\n".join(fake.paragraphs(nb=3)),
            description_conditions="\n".join(fake.paragraphs(nb=2)),
            ideal_profile="\n".join(fake.paragraphs(nb=2)),
            questions_json=questions,
            soft_questions_json=soft_questions,
            is_active=random.choice([True, True, True, False]),  # 75% вероятность активной вакансии
            created_at=fake.date_time_between(start_date='-60d', end_date='now', tzinfo=timezone.utc),
            created_by=hr.id
        )
        
        db.session.add(vacancy)
    
    db.session.commit()
    print(f"Создано {num_vacancies - existing_count} вакансий")

def create_notifications(num_notifications=50):
    """Создание уведомлений для кандидатов"""
    # Проверяем, есть ли кандидаты
    candidates = Candidate.query.all()
    if not candidates:
        print("Нет кандидатов для уведомлений. Сначала создайте кандидатов.")
        return
    
    existing_count = Notification.query.count()
    if existing_count >= num_notifications:
        print(f"Уже существует {existing_count} уведомлений. Пропускаем создание.")
        return
    
    notification_types = Notification.get_notification_types()
    
    for _ in tqdm(range(num_notifications - existing_count), desc="Создание уведомлений"):
        candidate = random.choice(candidates)
        notification_type = random.choice(notification_types)
        
        if notification_type == "application_received":
            message = f"Ваша заявка на вакансию '{candidate.vacancy.title}' принята. Мы свяжемся с вами после рассмотрения."
        elif notification_type == "status_update":
            message = f"Статус вашей заявки на вакансию '{candidate.vacancy.title}' изменен на '{candidate.c_candidate_status.name}'."
        elif notification_type == "interview_invitation":
            date = fake.date_time_between(start_date='+1d', end_date='+14d', tzinfo=timezone.utc)
            message = f"Приглашаем вас на собеседование по вакансии '{candidate.vacancy.title}'. Дата: {date.strftime('%d.%m.%Y %H:%M')}."
        elif notification_type == "rejection":
            message = f"К сожалению, ваша кандидатура на вакансию '{candidate.vacancy.title}' была отклонена. Благодарим за интерес к нашей компании."
        elif notification_type == "offer":
            message = f"Поздравляем! Вам сделано предложение о работе на позицию '{candidate.vacancy.title}'. Ожидаем вашего ответа."
        
        notification = Notification(
            candidate_id=candidate.id,
            type=notification_type,
            message=message,
            email_sent=random.choice([True, False]),
            created_at=fake.date_time_between(start_date='-30d', end_date='now', tzinfo=timezone.utc)
        )
        
        db.session.add(notification)
    
    db.session.commit()
    print(f"Создано {num_notifications - existing_count} уведомлений")

def create_system_logs(num_logs=100):
    """Создание системных логов"""
    users = User.query.all()
    if not users:
        print("Нет пользователей для создания логов. Сначала создайте пользователей.")
        return
    
    existing_count = SystemLog.query.count()
    if existing_count >= num_logs:
        print(f"Уже существует {existing_count} логов. Пропускаем создание.")
        return
    
    event_types = [
        "login", "logout", "create_vacancy", "update_vacancy", 
        "create_candidate", "update_candidate", "delete_candidate",
        "send_notification", "password_reset", "export_data",
        "admin_login", "api_access", "candidate_status_change"
    ]
    
    ip_addresses = [
        "192.168.1.1", "10.0.0.1", "172.16.0.1", "127.0.0.1",
        "95.161.223.45", "78.29.101.22", "45.67.89.123", "209.85.231.104"
    ]
    
    # Используем прямое создание логов через метод SystemLog.log
    for _ in tqdm(range(num_logs - existing_count), desc="Создание системных логов"):
        user = random.choice(users)
        event_type = random.choice(event_types)
        
        # Используем full_name вместо email для избежания проблем с дешифрованием
        if event_type == "login":
            description = f"Вход в систему пользователя ID={user.id}, {user.full_name}"
        elif event_type == "logout":
            description = f"Выход из системы пользователя ID={user.id}, {user.full_name}"
        elif event_type == "create_vacancy":
            description = f"Создана новая вакансия пользователем ID={user.id}, {user.full_name}"
        elif event_type == "update_vacancy":
            description = f"Обновлена вакансия пользователем ID={user.id}, {user.full_name}"
        elif event_type == "create_candidate":
            description = f"Добавлен новый кандидат пользователем ID={user.id}, {user.full_name}"
        elif event_type == "update_candidate":
            description = f"Обновлена информация о кандидате пользователем ID={user.id}, {user.full_name}"
        elif event_type == "delete_candidate":
            description = f"Удален кандидат пользователем ID={user.id}, {user.full_name}"
        elif event_type == "send_notification":
            description = f"Отправлено уведомление кандидату пользователем ID={user.id}, {user.full_name}"
        elif event_type == "password_reset":
            description = f"Запрос на сброс пароля от пользователя ID={user.id}, {user.full_name}"
        elif event_type == "export_data":
            description = f"Экспорт данных пользователем ID={user.id}, {user.full_name}"
        elif event_type == "admin_login":
            description = f"Вход в административную панель пользователем ID={user.id}, {user.full_name}"
        elif event_type == "api_access":
            description = f"Доступ к API пользователем ID={user.id}, {user.full_name}"
        elif event_type == "candidate_status_change":
            description = f"Изменен статус кандидата пользователем ID={user.id}, {user.full_name}"
        
        # Используем статический метод log вместо прямого создания объекта
        SystemLog.log(
            event_type=event_type,
            description=description,
            user_id=user.id,
            ip_address=random.choice(ip_addresses)
        )
    
    print(f"Создано логов: {num_logs - existing_count}")

def main():
    """Основная функция для заполнения базы данных тестовыми данными"""
    print("Начало заполнения базы данных...")
    
    # Создание справочников
    create_c_gender()
    create_c_user_status()
    create_c_candidate_status()
    create_c_employment_type()
    
    # Создание пользователей
    create_admin_user()
    create_hr_users(5)
    
    # Создание вакансий и кандидатов
    create_vacancies(10)
    create_candidates(30)
    
    # Создание уведомлений и логов
    create_notifications(50)
    create_system_logs(100)
    
    print("База данных успешно заполнена тестовыми данными!")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        main() 