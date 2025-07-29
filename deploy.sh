#!/bin/bash
# Keep it same as deploy.sh in the repo untill we switch to docker containers

set -e; # Exit on error

cd /home/cto-tool/cto-tool

# Enable maintenance mode
touch maintenance.enabled

# Checkout release commit
git status
git remote set-url origin git@github.com-cto-tool:Semalab/cto-tool.git
git fetch --all
git checkout --force ${{ github.sha }}

# Build Vue
cd vue-frontend
npm install
npm run build
cd ..

# Update dependencies
uv sync --locked

# Run Django migrations
USE_REPLICA_DATABASE=False
uv run --locked python3 manage.py migrate

# Add version to filenames of static files
uv run --locked python3 manage.py collectstatic --noinput

# Init groups and permissions
uv run --locked python3 manage.py init_groups

# Changing files ownership to cto-tool
chown -R cto-tool:www-data /home/cto-tool/cto-tool/*
chmod -R 770 /home/cto-tool/cto-tool/*

# Update Apache configuration
cp apache.conf /etc/apache2/sites-available/000-default.conf
/etc/init.d/apache2 reload

# Disable maintenance mode
rm maintenance.enabled
