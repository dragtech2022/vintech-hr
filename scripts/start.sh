#!/bin/sh
set -eu
umask 077
python manage.py init
exec gunicorn --bind 0.0.0.0:8000 --workers 2 --threads 2 --timeout 30 --worker-tmp-dir /tmp --access-logfile - --error-logfile - wsgi:app
