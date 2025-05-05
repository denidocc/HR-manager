#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import current_app, render_template
from flask_mail import Message
from app import mail
import jwt
from time import time

def send_email(subject, sender, recipients, text_body, html_body):
    """Общая функция для отправки email"""
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    
    # Асинхронная отправка через Celery (если настроено)
    if current_app.config.get('USE_CELERY', False):
        from app.tasks import send_async_email
        send_async_email.delay(msg)
    else:
        mail.send(msg)

def send_password_reset_email(user):
    """Отправка письма для сброса пароля"""
    token = user.generate_reset_password_token()
    send_email(
        subject='Сброс пароля',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email],
        text_body=render_template('email/reset_password.txt',
                                 user=user, token=token),
        html_body=render_template('email/reset_password.html',
                                 user=user, token=token)
    )

def send_status_change_notification(candidate, notification):
    """Отправка уведомления о изменении статуса кандидата"""
    send_email(
        subject=f'Обновление статуса заявки: {candidate.vacancy.title}',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[candidate.email],
        text_body=render_template('email/status_change.txt',
                                 candidate=candidate,
                                 notification=notification),
        html_body=render_template('email/status_change.html',
                                 candidate=candidate,
                                 notification=notification)
    ) 