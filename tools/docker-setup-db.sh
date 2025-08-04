#!/bin/bash
# set -eu
python manage.py makemigrations
python manage.py migrate

if [ ${SAO_PROFILE} = "prod" ]; then
    python manage.py collectstatic --noinput
    chown -R ${SAO_APPUSER}:${SAO_APPUSER} /app/static
fi

# $DJANGO_SUPERUSER_PASSWORDがなければエラーを出して終了
if [ -z "${DJANGO_SUPERUSER_PASSWORD}" ]; then
    echo "❌ DJANGO_SUPERUSER_PASSWORD is not set. Aborting setup."
    exit 1
fi

# setup inital data
mkdir -p /app/docker-entrypoint-initdb.d
envsubst < db-init/init.template.sql > /app/docker-entrypoint-initdb.d/init.sql
