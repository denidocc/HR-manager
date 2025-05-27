from flask_wtf import FlaskForm
from wtforms import SelectField, BooleanField
from wtforms.validators import DataRequired

class SelectionStageForm(FlaskForm):
    """Форма для выбора этапа отбора из справочника"""
    stage = SelectField('Этап отбора', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Активен', default=True) 