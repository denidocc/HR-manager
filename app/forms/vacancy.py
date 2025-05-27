#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError
import json

class VacancyForm(FlaskForm):
    """Форма для создания и редактирования вакансии"""
    title = StringField('Название вакансии', validators=[
        DataRequired(message='Введите название вакансии'),
        Length(min=3, max=100, message='Название должно содержать от 3 до 100 символов')
    ])
    
    id_c_employment_type = SelectField('Тип занятости', 
        validators=[DataRequired(message='Выберите тип занятости')], 
        coerce=lambda x: int(x) if x is not None and x != '' else None
    )
    
    description_tasks = TextAreaField('Описание задач', validators=[
        DataRequired(message='Введите описание задач'),
        Length(min=10, message='Описание задач должно содержать минимум 10 символов')
    ])
    
    description_conditions = TextAreaField('Условия работы', validators=[
        DataRequired(message='Введите условия работы'),
        Length(min=10, message='Условия работы должны содержать минимум 10 символов')
    ])
    
    ideal_profile = TextAreaField('Идеальный кандидат', validators=[
        DataRequired(message='Введите описание идеального кандидата'),
        Length(min=10, message='Описание идеального кандидата должно содержать минимум 10 символов')
    ])
    
    questions_json = HiddenField('Профессиональные вопросы')
    soft_questions_json = HiddenField('Вопросы на soft skills')
    
    is_active = BooleanField('Активна')
    
    is_ai_generated = HiddenField('Генерация с помощью ИИ')
    ai_generation_date = HiddenField('Дата генерации')
    ai_generation_prompt = HiddenField('Промпт генерации')
    ai_generation_metadata = HiddenField('Метаданные генерации')
    
    submit = SubmitField('Сохранить')
    
    def validate_questions_json(self, field):
        """Валидация JSON с вопросами"""
        if field.data:
            try:
                questions = json.loads(field.data)
                if not isinstance(questions, list):
                    raise ValidationError('Некорректный формат вопросов')
                
                for q in questions:
                    if not isinstance(q, dict) or 'id' not in q or 'text' not in q:
                        raise ValidationError('Некорректный формат вопроса')
            except json.JSONDecodeError:
                raise ValidationError('Некорректный JSON-формат')
                
    def validate_id_c_employment_type(self, field):
        """Валидация выбора типа занятости"""
        if field.data is None:
            raise ValidationError('Выберите тип занятости')
        # Значение 0 теперь допустимо, так как это "Неизвестно"

    def process_formdata(self, valuelist):
        """Преобразование строковых булевых значений в настоящие булевы значения"""
        super().process_formdata(valuelist)
        if hasattr(self, 'is_ai_generated') and self.is_ai_generated.data:
            self.is_ai_generated.data = self.is_ai_generated.data.lower() == 'true'
        if hasattr(self, 'is_active') and self.is_active.data:
            self.is_active.data = self.is_active.data.lower() == 'true'

class VacancyAIGeneratorForm(FlaskForm):
    """Мини-форма для генерации вакансии с помощью ИИ"""
    title = StringField('Название вакансии', validators=[
        DataRequired(message='Введите название вакансии'),
        Length(min=3, max=100, message='Название должно содержать от 3 до 100 символов')
    ])
    
    id_c_employment_type = SelectField('Тип занятости', 
        validators=[DataRequired(message='Выберите тип занятости')],
        coerce=lambda x: int(x) if x is not None and x != '' else None
    )
    
    description_tasks = TextAreaField('Описание задач (кратко)', validators=[
        DataRequired(message='Введите краткое описание задач'),
        Length(min=20, message='Описание задач должно содержать минимум 20 символов')
    ])
    
    description_conditions = TextAreaField('Условия работы (кратко)', validators=[
        DataRequired(message='Введите краткие условия работы'),
        Length(min=20, message='Условия работы должны содержать минимум 20 символов')
    ])
    
    is_ai_generated = HiddenField('Генерация с помощью ИИ')
    ai_generation_date = HiddenField('Дата генерации')
    ai_generation_prompt = HiddenField('Промпт генерации')
    ai_generation_metadata = HiddenField('Метаданные генерации')
    
    submit = SubmitField('Сгенерировать вакансию')
    
    def validate_id_c_employment_type(self, field):
        """Валидация выбора типа занятости"""
        if field.data is None:
            raise ValidationError('Выберите тип занятости')
        # Значение 0 теперь допустимо, так как это "Неизвестно"