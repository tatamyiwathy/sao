#!/bin/bash
# set -eu
python manage.py makemigrations
python manage.py migrate
# python manage.py collectstatic
# chown -R www-data:www-data /app/static

# $DJANGO_SUPERUSER_PASSWORDがなければエラーを出して終了
if [ -z "${DJANGO_SUPERUSER_PASSWORD}" ]; then
    echo "❌ DJANGO_SUPERUSER_PASSWORD is not set. Aborting setup."
    exit 1
fi

python /app/is-superuser.py
if [ $? -ne 0 ]; then
    echo "Creating superuser..."
    python manage.py createsuperuser --noinput
    echo "Superuser created."
else
    echo "Superuser already exists. Skipping creation."
fi
