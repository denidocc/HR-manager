import os
from app import create_app, db
from app.models import User, Vacancy, Candidate, Notification, SystemLog

app = create_app(os.getenv('FLASK_ENV', 'default'))

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'User': User, 
        'Vacancy': Vacancy, 
        'Candidate': Candidate, 
        'Notification': Notification,
        'SystemLog': SystemLog
    }

if __name__ == '__main__':
    app.run(debug=True)