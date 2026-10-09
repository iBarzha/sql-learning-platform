#!/usr/bin/env bash
# Start the platform for a demo: one command, one published port, plain HTTP.
#
#   ./demo-up.sh                         fresh database with the demo course
#   DEMO_PORT=9000 ./demo-up.sh          publish on another port (default 8080)
#   DEMO_DUMP=path/to/dump.sql ./demo-up.sh   start from a pg_dump of the old server
#
# Everything it creates is removed by ./demo-down.sh.

set -eu
cd "$(dirname "$0")"

ENV_FILE=.env.demo
COMPOSE="docker compose --env-file $ENV_FILE -f docker-compose.demo.yml"

random_string() (
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$1" || true
)

if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" <<EOF
DEMO_PORT=${DEMO_PORT:-8080}
DEMO_PASSWORD=${DEMO_PASSWORD:-$(random_string 12)}
DEMO_ALLOWED_HOSTS=*
SECRET_KEY=$(random_string 50)
DB_PASSWORD=$(random_string 24)
MARIADB_ROOT_PASSWORD=$(random_string 24)
GEMINI_API_KEY=${GEMINI_API_KEY:-}
EOF
    chmod 600 "$ENV_FILE"
    echo "Created $ENV_FILE"
fi

value_of() { grep -E "^$1=" "$ENV_FILE" | head -n 1 | cut -d= -f2-; }
PORT=$(value_of DEMO_PORT)
PASSWORD=$(value_of DEMO_PASSWORD)

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

if [ -n "${DEMO_DUMP:-}" ]; then
    [ -f "$DEMO_DUMP" ] || { echo "Dump not found: $DEMO_DUMP"; exit 1; }
    echo "Restoring $DEMO_DUMP..."
    $COMPOSE up -d db
    wait_for db 90
    # \restrict and \unrestrict are written by recent pg_dump; older psql rejects them.
    grep -v -E '^\\(un)?restrict' "$DEMO_DUMP" \
        | $COMPOSE exec -T -e PGPASSWORD="$(value_of DB_PASSWORD)" db \
            psql -q -v ON_ERROR_STOP=0 -U postgres -d sql_learning > /dev/null
fi

echo "Starting services..."
$COMPOSE up -d
wait_for backend 240

echo "Loading demo data..."
if [ -n "${DEMO_DUMP:-}" ]; then
    $COMPOSE exec -T backend python manage.py seed_demo --set-passwords
else
    $COMPOSE exec -T backend python manage.py seed_demo
fi

ADDRESS=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
echo "Ready: http://${ADDRESS:-<server address>}:$PORT"
echo "Password for all demo accounts: $PASSWORD"
echo "Stop and remove everything: ./demo-down.sh"
