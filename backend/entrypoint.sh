#!/bin/sh
set -eu

# Migrations need DDL rights, so they run as the owner role...
DB_USER="$DB_OWNER_USER" DB_PASSWORD="$DB_OWNER_PASSWORD" \
    python manage.py migrate --noinput

# ...while the server itself runs as the DML-only app role.
exec gunicorn backend.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --access-logfile -
