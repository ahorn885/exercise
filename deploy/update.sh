#!/bin/bash
# Pull latest code and restart the service.
# Run from TrueNAS Shell whenever you want to deploy updates.

APP_DIR="/mnt/data/exercise"
VENV="$APP_DIR/.venv"

echo "Pulling latest code..."
git -C "$APP_DIR" pull origin main

echo "Updating dependencies..."
"$VENV/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "Restarting service..."
systemctl restart exercise-app

echo "Done. Status:"
systemctl status exercise-app --no-pager -l
