#!/bin/bash
set -e

# Configuration
VPS_HOST="niemenmaa-vps"
VPS_PATH="/home/niemenmaa-vps"
APP_NAME="ruokalista"

echo "Deploying $APP_NAME to VPS..."

# Sync code to VPS (exclude unnecessary files, preserve Dockerfile)
echo "Syncing files..."
rsync -avz --delete \
    --exclude '.git' \
    --exclude '.gitmodules' \
    --exclude '__pycache__' \
    --exclude 'venv' \
    --exclude '.venv' \
    --exclude '*.pyc' \
    --exclude 'data.db' \
    --exclude '.env' \
    --exclude '.claude' \
    --exclude '.serena' \
    --exclude 'Dockerfile' \
    ./ "$VPS_HOST:$VPS_PATH/apps/$APP_NAME/"

# Build and restart container on VPS
echo "Building and restarting container..."
ssh "$VPS_HOST" "cd $VPS_PATH && docker compose build $APP_NAME && docker compose up -d $APP_NAME"

echo "Done! Checking container status..."
ssh "$VPS_HOST" "docker ps --filter name=$APP_NAME --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
