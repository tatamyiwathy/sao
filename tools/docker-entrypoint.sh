#!/bin/bash

echo "###################Starting Docker entrypoint script..."
# Wait for the database to be ready and then run the setup script
set -e

if [ "$SAO_PROFILE" == "dev" ]; then
    tools/wait-for-it.sh db:${DB_PORT} --strict --timeout=60 -- tools/docker-setup-db.sh
    exec tools/run
    # exec bash
else
    tools/docker-setup-db.sh
    exec apache2ctl -D FOREGROUND
fi
echo "###################Docker entrypoint script completed."