#!/usr/bin/env bash
# ==============================================================
#  Case Management System — Ubuntu 22.04 Automated Setup
#  Usage: sudo bash setup.sh
# ==============================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_USER="cms"
APP_DIR="/opt/cms"
DATA_DIR="/var/lib/cms"
LOG_DIR="/var/log/cms"
DB_NAME="cms_production"
DB_USER="cms_user"
NODE_VERSION="20"
PYTHON_VERSION="3.11"

info()    { echo -e "\e[32m[INFO]\e[0m  $*"; }
warn()    { echo -e "\e[33m[WARN]\e[0m  $*"; }
error()   { echo -e "\e[31m[ERROR]\e[0m $*" >&2; exit 1; }

# ── Root check ────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || error "Run as root: sudo bash $0"

# ── System packages ───────────────────────────────────────────
info "Updating system packages…"
apt-get update -qq
apt-get install -y -qq \
    curl wget git build-essential \
    python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python3-pip \
    postgresql postgresql-contrib \
    nginx \
    redis-server \
    certbot python3-certbot-nginx \
    ufw fail2ban \
    supervisor \
    2>/dev/null

# ── Node.js via NodeSource ────────────────────────────────────
if ! command -v node &>/dev/null; then
    info "Installing Node.js ${NODE_VERSION}…"
    curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash -
    apt-get install -y nodejs
fi
info "Node $(node --version) / npm $(npm --version)"

# ── Application user ──────────────────────────────────────────
if ! id "$APP_USER" &>/dev/null; then
    info "Creating system user '${APP_USER}'…"
    useradd --system --shell /bin/false --home "$APP_DIR" --create-home "$APP_USER"
fi

# ── Directories ───────────────────────────────────────────────
info "Creating application directories…"
mkdir -p "${APP_DIR}/backend" "${APP_DIR}/frontend"
mkdir -p "${DATA_DIR}/uploads" "${DATA_DIR}/backups"
mkdir -p "${LOG_DIR}"
chown -R "${APP_USER}:${APP_USER}" "$APP_DIR" "$DATA_DIR" "$LOG_DIR"

# ── PostgreSQL ────────────────────────────────────────────────
info "Configuring PostgreSQL…"
systemctl enable --now postgresql

DB_PASS=$(openssl rand -hex 24)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

info "PostgreSQL credentials:"
info "  DB_USER = ${DB_USER}"
info "  DB_PASS = ${DB_PASS}   ← save this!"
info "  DB_NAME = ${DB_NAME}"

# ── Redis ─────────────────────────────────────────────────────
info "Enabling Redis…"
systemctl enable --now redis-server

# ── Backend: Python virtual environment ───────────────────────
info "Setting up Python virtual environment…"
VENV_DIR="${APP_DIR}/backend/venv"
python${PYTHON_VERSION} -m venv "$VENV_DIR"
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip wheel

if [[ -f "${REPO_DIR}/backend/requirements.txt" ]]; then
    "${VENV_DIR}/bin/pip" install --quiet -r "${REPO_DIR}/backend/requirements.txt"
else
    warn "backend/requirements.txt not found — skipping pip install"
fi

# ── Copy application files ────────────────────────────────────
info "Copying application files to ${APP_DIR}…"
rsync -a --delete \
    --exclude="*.pyc" --exclude="__pycache__" \
    --exclude=".env*" --exclude="venv" --exclude=".git" \
    "${REPO_DIR}/backend/" "${APP_DIR}/backend/"

rsync -a --delete \
    --exclude=".env*" --exclude="node_modules" --exclude=".git" \
    "${REPO_DIR}/frontend/" "${APP_DIR}/frontend/"

chown -R "${APP_USER}:${APP_USER}" "$APP_DIR"

# ── Frontend: build ───────────────────────────────────────────
info "Building Next.js frontend…"
FRONTEND="${APP_DIR}/frontend"
if [[ -f "${FRONTEND}/package.json" ]]; then
    cd "$FRONTEND"
    npm ci --silent
    npm run build
    cd -
else
    warn "frontend/package.json not found — skipping build"
fi

# ── .env.production ───────────────────────────────────────────
ENV_FILE="${APP_DIR}/.env.production"
if [[ ! -f "$ENV_FILE" ]]; then
    info "Creating .env.production template at ${ENV_FILE}…"
    cp "${REPO_DIR}/scripts/shared/.env.production.example" "$ENV_FILE"
    # Auto-fill the generated DB password
    sed -i "s|cms_user:CHANGE_ME@|cms_user:${DB_PASS}@|" "$ENV_FILE"
    SECRET=$(openssl rand -hex 32)
    sed -i "s|CHANGE_ME_use_openssl_rand_hex_32|${SECRET}|" "$ENV_FILE"
    chown root:${APP_USER} "$ENV_FILE"
    chmod 640 "$ENV_FILE"
    warn "Edit ${ENV_FILE} to complete the configuration (SMTP, domain, etc.)"
fi

# ── Database migrations ───────────────────────────────────────
info "Running Alembic migrations…"
cd "${APP_DIR}/backend"
set -a; source "${ENV_FILE}"; set +a
"${VENV_DIR}/bin/alembic" upgrade head || warn "Migrations failed — run manually after configuring .env.production"

# ── Firewall ──────────────────────────────────────────────────
info "Configuring UFW firewall…"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 'Nginx Full'
ufw --force enable

# ── Fail2ban ──────────────────────────────────────────────────
info "Enabling fail2ban…"
systemctl enable --now fail2ban

# ── Services ──────────────────────────────────────────────────
info "Installing systemd services…"
bash "${REPO_DIR}/scripts/linux/install-services.sh"

# ── Nginx ─────────────────────────────────────────────────────
info "Configuring Nginx…"
bash "${REPO_DIR}/scripts/linux/configure-nginx.sh"

# ── Cron: backups ─────────────────────────────────────────────
info "Installing daily backup cron job…"
BACKUP_SCRIPT="${REPO_DIR}/scripts/linux/backup.sh"
chmod +x "$BACKUP_SCRIPT"
crontab -l 2>/dev/null | grep -v "$BACKUP_SCRIPT" | { cat; echo "0 2 * * * $BACKUP_SCRIPT >> ${LOG_DIR}/backup.log 2>&1"; } | crontab -

info "✓ Setup complete!"
info "  1. Edit ${ENV_FILE} with your real SMTP / domain values"
info "  2. Run: sudo certbot --nginx -d yourdomain.com"
info "  3. Restart services: sudo systemctl restart cms-backend cms-frontend"
