#!/bin/bash

echo "###################Starting Docker entrypoint script..."
# Wait for the database to be ready and then run the setup script
set -e
tools/wait-for-it.sh db:${DB_PORT} --strict --timeout=60 -- tools/docker-setup-db.sh

if [ "$SAO_PROFILE" == "dev" ]; then
    exec tools/run
    # exec bash
else
    exec apache2ctl -D FOREGROUND
fi
echo "###################Docker entrypoint script completed."