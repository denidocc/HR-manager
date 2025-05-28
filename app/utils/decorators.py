import time
import functools
from flask import current_app, flash, redirect, url_for
from flask_login import current_user
from functools import wraps

def profile_time(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        current_app.logger.info(f"Функция {func.__name__} выполнилась за {execution_time:.2f} секунд")
        return result
    return wrapper 

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('У вас нет прав для доступа к этой странице', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function 