"""Gunicorn entry: gunicorn --workers 1 --bind 0.0.0.0:$PORT api.wsgi:app"""

from api.app import create_app

app = create_app()
