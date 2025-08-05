#!/bin/bash
set -e

# テスト環境フラグで判定
if [ "${IS_TEST}" = "true" ] || [ "${DJANGO_SETTINGS_MODULE}" = "sao_proj.test_settings" ]; then
    echo "🧪 Test environment detected - skipping database setup"
    exec "$@"
    exit 0
fi


# python manage.py makemigrations --noinput
python manage.py migrate

# $DJANGO_SUPERUSER_PASSWORDがなければエラーを出して終了
if [ -z "${DJANGO_SUPERUSER_PASSWORD}" ]; then
    echo "❌ DJANGO_SUPERUSER_PASSWORD is not set. Aborting setup."
    exit 1
fi

if python /app/is-superuser.py; then
    echo "✅ Superuser already exists. Skipping creation."
else
    echo "🔨 Creating superuser..."
    python manage.py createsuperuser --noinput
fi
