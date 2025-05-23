#!/usr/bin/env python
# -*- coding: utf-8 -*-
import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from faker import Faker
from app import create_app, db
from app.models import User, Vacancy, Candidate, Notification, SystemLog, User_Selection_Stage
from app.models import C_Gender, C_User_Status, C_Selection_Stage, C_Employment_Type, C_Education
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

def create_c_education():
    """Создание справочника образований"""
    educations = [
        {'name': 'Не указан', 'short_name': 'Н/У'},
        {'name': 'Среднее', 'short_name': 'Ср'},
        {'name': 'Среднее специальное', 'short_name': 'СП'},
        {'name': 'Высшее', 'short_name': 'Высш'},
        {'name': 'Магистратура', 'short_name': 'Маг'},
        {'name': 'Аспирантура', 'short_name': 'Аспир'},
        {'name': 'Ученая степень', 'short_name': 'Ученая степень'},
        {'name': 'Другое', 'short_name': 'Другое'}
    ]
    for i, education in enumerate(educations):
        create_if_not_exists(C_Education, education['name'], i, short_name=education['short_name'])
    db.session.commit()
    print("Справочник образований успешно создан")

def create_c_user_status():
    """Создание справочника статусов пользователей"""
    # Запрашиваем все существующие статусы
    existing_statuses = {}
    for status in C_User_Status.query.all():
        existing_statuses[status.name] = status
    
    # Определяем нужные статусы
    statuses = [
        {'id': 0, 'name': 'Неизвестно', 'description': 'Статус не определен'},
        {'id': 1, 'name': 'Активный', 'description': 'Пользователь активен'},
        {'id': 2, 'name': 'Ожидает подтверждения', 'description': 'Пользователь ожидает активации администратором'},
        {'id': 3, 'name': 'Отклонен', 'description': 'Заявка пользователя отклонена администратором'},
        {'id': 4, 'name': 'Неактивный', 'description': 'Пользователь временно неактивен'},
        {'id': 5, 'name': 'Заблокирован', 'description': 'Пользователь заблокирован'},
        {'id': 6, 'name': 'Удален', 'description': 'Пользователь удален из системы'}
    ]
    
    # Обновляем существующие или создаем новые
    for status_data in statuses:
        if status_data['name'] in existing_statuses:
            # Обновляем существующий статус, если нужно
            status = existing_statuses[status_data['name']]
            if status.description != status_data['description']:
                status.description = status_data['description']
            # Пропускаем обновление ID, так как оно может вызвать конфликты
        else:
            # Создаем новый статус
            new_status = C_User_Status(
                id=status_data['id'],
                name=status_data['name'],
                description=status_data['description']
            )
            db.session.add(new_status)
    
    # Сохраняем изменения
    try:
        db.session.commit()
        print("Справочник статусов пользователей успешно обновлен")
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при обновлении справочника статусов пользователей: {e}")

def create_c_selection_stage():
    """Создание справочника этапов отбора"""
    from app.models.c_selection_status import C_Selection_Status
    
    # Сначала создаем статусы
    statuses = [
        {'name': 'Неизвестно', 'code': 'UNKNOWN', 'description': 'Статус не определен'},
        {'name': 'Новый', 'code': 'NEW', 'description': 'Новая заявка'},
        {'name': 'В процессе', 'code': 'IN_PROGRESS', 'description': 'Кандидат в процессе отбора'},
        {'name': 'Отклонен', 'code': 'REJECT', 'description': 'Кандидат отклонен'},
        {'name': 'Принят', 'code': 'ACCEPT', 'description': 'Кандидат принят'}
    ]
    
    status_map = {}
    for status_data in statuses:
        status = create_if_not_exists(C_Selection_Status, status_data['name'], 
                                    code=status_data['code'],
                                    description=status_data['description'])
        status_map[status.code] = status
    
    # Теперь создаем этапы
    stages = [
        {'name': 'Заявка подана', 'description': 'Кандидат только что подал заявку', 'color': '#3498db', 'order': 1, 'status_code': 'NEW'},
        {'name': 'Рассмотрение резюме', 'description': 'Резюме кандидата находится на рассмотрении', 'color': '#17a2b8', 'order': 2, 'status_code': 'IN_PROGRESS'},
        {'name': 'Назначено интервью', 'description': 'Кандидату назначено собеседование', 'color': '#f39c12', 'order': 3, 'status_code': 'IN_PROGRESS'},
        {'name': 'Ожидает решения', 'description': 'Кандидат ожидает решения после интервью', 'color': '#9b59b6', 'order': 4, 'status_code': 'IN_PROGRESS'},
        {'name': 'Принят', 'description': 'Кандидат принят на работу', 'color': '#2ecc71', 'order': 5, 'status_code': 'ACCEPT'},
        {'name': 'Отклонен', 'description': 'Кандидат не прошел отбор', 'color': '#e74c3c', 'order': 6, 'status_code': 'REJECT'}
    ]
    
    for stage_data in stages:
        existing = C_Selection_Stage.query.filter_by(name=stage_data['name']).first()
        if not existing:
            new_stage = C_Selection_Stage(
                name=stage_data['name'],
                description=stage_data['description'],
                color=stage_data['color'],
                order=stage_data['order'],
                is_standard=True,
                is_active=True,
                id_c_selection_status=status_map[stage_data['status_code']].id
            )
            db.session.add(new_stage)
    
    db.session.commit()
    print("Справочник этапов отбора успешно создан")

def create_c_employment_type():
    """Создание справочника типов занятости"""
    employment_types = [
        {'id': 0, 'name': 'Неизвестно', 'description': 'Статус не определен'},
        {'id': 1, 'name': 'Полный день', 'description': 'Работа с 9 до 18'},
        {'id': 2, 'name': 'Неполный день', 'description': 'Частичная занятость'},
        {'id': 3, 'name': 'Удаленно', 'description': 'Работа из дома'},
        {'id': 4, 'name': 'Гибкий график', 'description': 'Свободный график работы'},
        {'id': 5, 'name': 'Сменный график', 'description': 'Работа по сменам'}
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
    
    # Получаем всех HR-менеджеров
    hrs = User.query.filter_by(role='hr').all()
    if not hrs:
        print("Нет HR-менеджеров. Сначала создайте HR-менеджеров.")
        return
    
    # Получаем все этапы отбора
    stages = C_Selection_Stage.query.filter_by(is_standard=True).all()
    if not stages:
        print("Нет этапов отбора. Сначала создайте этапы отбора.")
        return
    
    existing_count = Candidate.query.count()
    if existing_count >= num_candidates:
        print(f"Уже существует {existing_count} кандидатов. Пропускаем создание.")
        return
    
    for _ in tqdm(range(num_candidates - existing_count), desc="Создание кандидатов"):
        # Выбираем случайного HR и вакансию
        hr = random.choice(hrs)
        vacancy = random.choice(vacancies)
        stage = random.choice(stages)
        
        # Создаем или получаем User_Selection_Stage для HR
        user_stage = User_Selection_Stage.query.filter_by(
            user_id=hr.id,
            stage_id=stage.id
        ).first()
        
        if not user_stage:
            user_stage = User_Selection_Stage(
                user_id=hr.id,
                stage_id=stage.id,
                order=stage.order,
                is_active=True
            )
            db.session.add(user_stage)
            db.session.flush()  # Получаем ID для user_stage
        
        candidate = Candidate(
            vacancy_id=vacancy.id,
            user_id=hr.id,
            stage_id=stage.id,
            full_name=fake.name(),
            email=fake.email(),
            phone=fake.phone_number(),
            base_answers={
                "location": random.choice(["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург"]),
                "experience_years": random.randint(0, 15),
                "education": random.choice(["Высшее", "Среднее специальное", "Среднее"]),
                "desired_salary": random.randint(50000, 300000),
                "gender": random.choice(["М", "Ж"])
            },
            vacancy_answers={},
            soft_answers={},
            cover_letter=fake.text(max_nb_chars=500),
            tracking_code=str(uuid.uuid4()),
            created_at=fake.date_time_between(start_date='-1y', end_date='now', tzinfo=timezone.utc)
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
            message = f"Статус вашей заявки на вакансию '{candidate.vacancy.title}' изменен на '{candidate.user_selection_stage.selection_stage.name}'."
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
    
    # Создаем справочники
    create_c_gender()
    create_c_education()
    create_c_user_status()
    create_c_selection_stage()
    create_c_employment_type()
    
    # Создаем пользователей
    create_admin_user()
    create_hr_users(5)
    
    # Создаем вакансии
    create_vacancies(10)
    
    # Создаем кандидатов
    create_candidates(30)
    
    # Создаем уведомления
    create_notifications(50)
    
    # Создаем системные логи
    create_system_logs(100)
    
    print("База данных успешно заполнена тестовыми данными!")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        main() 