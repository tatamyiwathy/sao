#!/bin/bash
set -e

# python manage.py makemigrations --noinput
python manage.py migrate

# $DJANGO_SUPERUSER_PASSWORDがなければエラーを出して終了
if [ -z "${DJANGO_SUPERUSER_PASSWORD}" ]; then
    echo "❌ DJANGO_SUPERUSER_PASSWORD is not set. Aborting setup."
    exit 1
fi

if python manage.py is_exits_superuser; then
    echo "✅ Superuser already exists. Skipping creation."
else
    echo "🔨 Creating superuser..."
    python manage.py createsuperuser --noinput
fi
