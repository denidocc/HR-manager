from flask import Blueprint, render_template
from app.utils.decorators import profile_time

index_bp = Blueprint('index', __name__)

@index_bp.route('/')
@index_bp.route('/index')
@profile_time
def index():
    return render_template('public/index.html', title='Home')