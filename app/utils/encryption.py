from sqlalchemy import func, cast
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
        
        return db.session.scalar(
            func.pgp_sym_decrypt(
                cast(encrypted_value, sa.LargeBinary),
                current_app.config['ENCRYPTION_KEY'],
                current_app.config.get('ENCRYPTION_OPTIONS', '')
            )
        )
    
    def setter(self, value):
        if value is None:
            setattr(self, f'_{field_name}', None)
            return
            
        setattr(
            self,
            f'_{field_name}',
            db.session.scalar(
                func.pgp_sym_encrypt(
                    value,
                    current_app.config['ENCRYPTION_KEY'],
                    current_app.config.get('ENCRYPTION_OPTIONS', '')
                )
            )
        )
    
    return property(getter, setter) 