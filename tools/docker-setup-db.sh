#!/bin/bash

python manage.py migrate
python manage.py collectstatic
chown -R www-data:www-data /app/static

# $DJANGO_SUPERUSER_PASSWORDがなければエラーを出して終了
if [ -z "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "❌ DJANGO_SUPERUSER_PASSWORD is not set. Aborting setup."
    exit 1
fi

python is-superuser.py
if [ $? -ne 0 ]; then
    echo "Creating superuser..."
    export DJANGO_SUPERUSER_USERNAME=saoadmin
    export DJANGO_SUPERUSER_EMAIL=qqq@qqq.com
    export DJANGO_SUPERUSER_PASSWORD=saoadmin
    python manage.py createsuperuser --noinput
    echo "Superuser created."
else
    echo "Superuser already exists. Skipping creation."
fi
