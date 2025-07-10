#!/bin/bash

echo "###################Starting Docker entrypoint script..."
# Wait for the database to be ready and then run the setup script
set -e
tools/wait-for-it.sh db:3306 --strict --timeout=60 -- tools/docker-setup-db.sh

if [ "$SAO_PROFILE" == "dev" ]; then
    echo "Running Django development server..."
    exec python ./manage.py runserver 0.0.0.0:8000
    # exec bash
else
    exec apache2ctl -D FOREGROUND
fi