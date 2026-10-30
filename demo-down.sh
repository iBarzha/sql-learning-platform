#!/usr/bin/env bash
# Stop the demo and delete its containers, volumes, images and generated passwords.

set -eu
cd "$(dirname "$0")"

ENV_FILE=.env.demo
[ -f "$ENV_FILE" ] || { echo "Nothing to remove: $ENV_FILE does not exist."; exit 0; }

docker compose --env-file "$ENV_FILE" -f docker-compose.demo.yml \
    down --volumes --rmi local --remove-orphans
rm -f "$ENV_FILE"
echo "Demo removed."
