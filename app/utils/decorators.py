import time
import functools
from flask import current_app

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