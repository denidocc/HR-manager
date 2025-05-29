from sqlalchemy import func, cast, text
import sqlalchemy as sa
from flask import current_app
from app import db

def encrypted_property(field_name):
    """
    Создает свойство для шифрованного поля с использованием pgp_sym_encrypt/decrypt PostgreSQL
    
    Использование:
    class User(db.Model):
        _email = db.Column(db.Text)
        email = encrypted_property('email')
    """
    def getter(self):
        encrypted_value = getattr(self, f'_{field_name}')
        if encrypted_value is None:
            return None
        
        try:
            # Используем func.pgp_sym_decrypt() - стандартный SQLAlchemy подход
            return db.session.scalar(
                func.pgp_sym_decrypt(
                    cast(encrypted_value, sa.LargeBinary),
                    current_app.config['ENCRYPTION_KEY'],
                    current_app.config.get('ENCRYPTION_OPTIONS', '')
                )
            )
        except Exception as e:
            current_app.logger.error(f"Error decrypting {field_name}: {str(e)}")
            db.session.rollback()  # Откатываем транзакцию при ошибке
            return None
    
    def setter(self, value):
        if value is None:
            setattr(self, f'_{field_name}', None)
            return
        
        try:
            # Используем func.pgp_sym_encrypt() - стандартный SQLAlchemy подход
            encrypted = db.session.scalar(
                func.pgp_sym_encrypt(
                    value,
                    current_app.config['ENCRYPTION_KEY'],
                    current_app.config.get('ENCRYPTION_OPTIONS', '')
                )
            )
            setattr(self, f'_{field_name}', encrypted)
        except Exception as e:
            current_app.logger.error(f"Error encrypting {field_name}: {str(e)}")
            db.session.rollback()  # Откатываем транзакцию при ошибке
            setattr(self, f'_{field_name}', None)
    
    return property(getter, setter) 