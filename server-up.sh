#!/usr/bin/env bash
# Start the platform on a shared server behind the host nginx (docker-compose.server.yml).
#
#   APP_HOST=sql.example.com ./server-up.sh    first start: creates .env.server with random
#                                              secrets, builds, starts, migrates, seeds
#   ./server-up.sh --update                    rebuild and restart after new code was copied
#                                              in; keeps the database and the secrets
#
# Optional on the first start: APP_PORT (loopback port the host nginx proxies to, default
# 8090), ENABLE_HTTPS (default True: the host nginx must serve the site over TLS),
# GEMINI_API_KEY. The host nginx side is described in docs/server-deploy.md.

set -eu
cd "$(dirname "$0")"

ENV_FILE=.env.server
COMPOSE="docker compose --env-file $ENV_FILE -f docker-compose.server.yml"
UPDATE=0
[ "${1:-}" = "--update" ] && UPDATE=1

random_string() (
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom 2>/dev/null | head -c "$1" || true
)

FIRST_RUN=0
if [ ! -f "$ENV_FILE" ]; then
    [ "$UPDATE" = 1 ] && { echo "$ENV_FILE is missing: run without --update first."; exit 1; }
    : "${APP_HOST:?APP_HOST=<domain> is required on the first start}"
    cat > "$ENV_FILE" <<EOF
APP_HOST=$APP_HOST
APP_PORT=${APP_PORT:-8090}
APP_SCHEME=$([ "${ENABLE_HTTPS:-True}" = "True" ] && echo https || echo http)
ENABLE_HTTPS=${ENABLE_HTTPS:-True}
DEMO_PASSWORD=${DEMO_PASSWORD:-$(random_string 14)}
SECRET_KEY=$(random_string 50)
DB_PASSWORD=$(random_string 24)
MARIADB_ROOT_PASSWORD=$(random_string 24)
SESSION_REDIS_PASSWORD=$(random_string 24)
GEMINI_API_KEY=${GEMINI_API_KEY:-}
EOF
    chmod 600 "$ENV_FILE"
    echo "Created $ENV_FILE"
    FIRST_RUN=1
fi

value_of() { grep -E "^$1=" "$ENV_FILE" | head -n 1 | cut -d= -f2-; }

wait_for() {
    # wait_for <service> <seconds>
    local waited=0
    until [ "$($COMPOSE ps --format '{{.Health}}' "$1" 2>/dev/null)" = "healthy" ]; do
        waited=$((waited + 3))
        if [ "$waited" -ge "$2" ]; then
            echo "Service '$1' did not become healthy in $2 s. Last log lines:"
            $COMPOSE logs --tail 40 "$1"
            exit 1
        fi
        sleep 3
    done
}

echo "Building images..."
$COMPOSE build

echo "Starting services..."
$COMPOSE up -d --remove-orphans
wait_for backend 240

if [ "$FIRST_RUN" = 1 ]; then
    echo "Loading the demo accounts and courses..."
    $COMPOSE exec -T backend python manage.py seed_demo
    $COMPOSE exec -T backend python manage.py seed_gruber --instructor instructor@test.com
fi

echo
echo "Ready on 127.0.0.1:$(value_of APP_PORT) for $(value_of APP_SCHEME)://$(value_of APP_HOST)"
if [ "$FIRST_RUN" = 1 ]; then
    echo "Password of admin@test.com, instructor@test.com, student@test.com, student2@test.com:"
    echo "  $(value_of DEMO_PASSWORD)"
fi
