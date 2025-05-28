from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

class SelectionStageForm(FlaskForm):
    """Форма для создания/редактирования этапа отбора"""
    name = StringField('Название', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Описание', validators=[Optional(), Length(max=500)])
    color = StringField('Цвет', validators=[DataRequired()], default='#6c757d')
    order = IntegerField('Порядок', validators=[Optional(), NumberRange(min=0)], default=0)
    is_standard = BooleanField('Стандартный этап', default=False)
    is_active = BooleanField('Активен', default=True)
    status_id = SelectField('Статус', coerce=int, validators=[DataRequired()])

class SelectionStatusForm(FlaskForm):
    """Форма для создания/редактирования статуса этапа отбора"""
    name = StringField('Название', validators=[DataRequired(), Length(min=2, max=100)])
    code = StringField('Код', validators=[DataRequired(), Length(min=2, max=50)])
    description = TextAreaField('Описание', validators=[Optional(), Length(max=500)])
    order = IntegerField('Порядок', validators=[Optional(), NumberRange(min=0)], default=0)
    is_active = BooleanField('Активен', default=True) 