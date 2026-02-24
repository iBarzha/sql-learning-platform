#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || true

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 60 --graceful-timeout 30 config.wsgi:application
