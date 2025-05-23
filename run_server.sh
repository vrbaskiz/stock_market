#!/bin/bash

# --- Load Environment Variables ---
# Use 'set -a' to automatically export all variables defined after it
# This ensures that variables from .env become true environment variables
# accessible by child processes (like Django).
set -a
source ./.env # Load environment variables from .env file
set +a # Turn off automatic export after sourcing .env

# --- Run Django Development Server ---
echo "Starting Django development server..."
python manage.py runserver "$@" # "$@" passes all arguments from start_dev.sh to runserver
