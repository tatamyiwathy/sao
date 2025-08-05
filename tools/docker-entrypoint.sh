#!/bin/bash

echo "###################Starting Docker entrypoint script..."
# Wait for the database to be ready and then run the setup script
set -e

# 権限確認
echo "🔍 Current user: $(whoami)"
echo "🔍 User ID: $(id)"

# テスト環境フラグでの判定
if [ "${IS_TEST}" = "true" ]; then
    echo "🧪 Test environment detected - skipping database setup"
    exec "$@"
    exit 0
fi

if [ -n "${MYSQL_HOST}" ] && [ "${MYSQL_HOST}" != "" ]; then
    # データベース接続を待つ
    tools/wait-for-it.sh ${MYSQL_HOST}:${MYSQL_PORT} \
        --strict --timeout=60 -- tools/docker-setup-db.sh
else
    echo "⚠️  No MySQL host specified - skipping database setup"
fi


if [ "$SAO_PROFILE" == "dev" ]; then
    exec tools/run
    # exec bash
elif [ "$SAO_PROFILE" == "prod" ]; then
    echo "🚀 Starting Gunicorn server..."
    exec gunicorn sao_proj.wsgi:application \
        --bind 0.0.0.0:10000 \
        --workers 2 \
        --timeout 60 \
        --access-logfile /var/log/sao/sao-access.log \
        --error-logfile /var/log/sao/sao-error.log \
        --log-level info \
        --user ${SAO_APPUSER:-saouser} \
        --group ${SAO_APPUSER:-saouser}
else
    echo "🚀 Starting Gunicorn (fallback)..."
    exec gunicorn sao_proj.wsgi:application --bind 0.0.0.0:10000
fi
echo "###################Docker entrypoint script completed."