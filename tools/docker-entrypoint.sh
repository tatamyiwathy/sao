#!/bin/bash

echo "###################Starting Docker entrypoint script..."
# Wait for the database to be ready and then run the setup script
set -e
tools/wait-for-it.sh db:3306 --strict --timeout=60 -- ./docker-setup-db.sh
exec apache2ctl -D FOREGROUND