#!/bin/bash
# SQL Learning Platform — DigitalOcean Droplet deployment script
# Run this on a fresh Ubuntu 24.04 droplet with Docker pre-installed
set -e

APP_DIR="/opt/sql-learning-platform"
REPO_URL="$1"
BRANCH="${2:-fix/pre-deploy-fixes}"

if [ -z "$REPO_URL" ]; then
    echo "Usage: bash deploy.sh <git-repo-url> [branch]"
    echo "Example: bash deploy.sh https://github.com/user/sql-learning-platform.git fix/pre-deploy-fixes"
    exit 1
fi

echo "=== SQL Learning Platform Deployment ==="

# 1. Install Docker Compose plugin if not present
if ! docker compose version &>/dev/null; then
    echo "Installing Docker Compose plugin..."
    apt-get update && apt-get install -y docker-compose-plugin
fi

# 2. Configure firewall
echo "Configuring firewall..."
ufw allow OpenSSH
ufw allow 80/tcp
ufw --force enable

# 3. Clone repo
echo "Cloning repository..."
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
else
    git clone -b "$BRANCH" "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# 4. Generate production .env
if [ ! -f .env ]; then
    echo "Generating production .env..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    MARIADB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    DROPLET_IP=$(curl -s http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address 2>/dev/null || hostname -I | awk '{print $1}')

    cat > .env <<EOF
SECRET_KEY=${SECRET_KEY}
DEBUG=False
DB_NAME=sql_learning
DB_USER=postgres
DB_PASSWORD=${DB_PASSWORD}
ALLOWED_HOSTS=${DROPLET_IP},localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://${DROPLET_IP}
VITE_API_URL=http://${DROPLET_IP}
MARIADB_ROOT_PASSWORD=${MARIADB_PASSWORD}
EOF
    echo "Generated .env with IP: ${DROPLET_IP}"
    echo "IMPORTANT: Review .env before continuing!"
    cat .env
    echo ""
    read -p "Press Enter to continue or Ctrl+C to abort..."
fi

# 5. Build and start services
echo "Building and starting services..."
docker compose --profile production build
docker compose --profile production up -d

# 6. Wait for backend to be healthy
echo "Waiting for backend to start..."
for i in $(seq 1 60); do
    if docker compose exec -T backend curl -sf http://localhost:8000/api/health/ &>/dev/null; then
        echo "Backend is healthy!"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "ERROR: Backend did not become healthy in 60s"
        docker compose logs backend --tail=50
        exit 1
    fi
    sleep 2
done

# 7. Create superuser
echo ""
echo "Creating admin superuser..."
docker compose exec -T backend python manage.py shell -c "
from users.models import User
if not User.objects.filter(email='admin@test.com').exists():
    u = User.objects.create_superuser(email='admin@test.com', username='admin', password='admin123')
    u.role = 'admin'
    u.first_name = 'Admin'
    u.last_name = 'User'
    u.save()
    print('Admin user created: admin@test.com / admin123')
else:
    print('Admin user already exists')
"

echo ""
echo "=== Deployment complete! ==="
DROPLET_IP=$(curl -s http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address 2>/dev/null || hostname -I | awk '{print $1}')
echo "Access your app at: http://${DROPLET_IP}"
echo ""
echo "Useful commands:"
echo "  docker compose --profile production logs -f      # View logs"
echo "  docker compose --profile production restart      # Restart all"
echo "  docker compose --profile production down         # Stop all"
echo "  docker compose --profile production up -d        # Start all"
