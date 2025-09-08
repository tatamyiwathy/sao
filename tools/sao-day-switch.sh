#!/bin/bash
# sao-day-switch.sh
# Usage: sao-day-switch.sh [YYYY-MM-DD]
# This script switches the working day in the SAO system to the specified date.
# If no date is provided, it switches to the current date.

set -e

DATE=${1:-$(date --date '1 day ago' +%Y-%m-%d)}
responce=`curl -s -X POST -d "date=$DATE" http://localhost:8000/sao/day_switch`
if [ "$responce"=="day switch done" ]; then
     echo "Day switch from $DATE completed successfully."
else
    echo "Day switch from $DATE failed. Response: $responce"
    exit 1
fi
