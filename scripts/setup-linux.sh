#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Case Management System — Linux/macOS setup script
# Verifies prerequisites, creates venv, and installs dependencies
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ─── Check prerequisites ─────────────────────────────────────────────────────

info "Checking prerequisites..."

# Python 3.11+
if ! command -v python3 &>/dev/null; then
    error "Python 3 is not installed. Install Python 3.11 or higher."
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    error "Python 3.11+ required. Found: $PYTHON_VERSION"
fi
info "Python $PYTHON_VERSION ✓"

# Node.js 18+
if ! command -v node &>/dev/null; then
    error "Node.js is not installed. Install Node.js 18 or higher."
fi
NODE_VERSION=$(node --version | sed 's/v//')
NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 18 ]; then
    error "Node.js 18+ required. Found: v$NODE_VERSION"
fi
info "Node.js v$NODE_VERSION ✓"

# npm
if ! command -v npm &>/dev/null; then
    error "npm is not installed."
fi
info "npm $(npm --version) ✓"

# PostgreSQL client (optional but recommended)
if command -v psql &>/dev/null; then
    info "PostgreSQL client $(psql --version | awk '{print $3}') ✓"
else
    warn "PostgreSQL client not found. Install postgresql-client for migrations."
fi

# Redis CLI (optional)
if command -v redis-cli &>/dev/null; then
    info "Redis CLI $(redis-cli --version | awk '{print $2}') ✓"
else
    warn "Redis CLI not found. Install redis-tools to test Redis connectivity."
fi

# ─── Backend setup ────────────────────────────────────────────────────────────

info "Setting up backend..."

cd "$PROJECT_ROOT/backend"

if [ ! -d "venv" ]; then
    info "Creating virtual environment..."
    python3 -m venv venv
fi

info "Activating venv and installing dependencies..."
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements-dev.txt --quiet
info "Backend dependencies installed ✓"

if [ ! -f ".env" ]; then
    cp .env.example .env
    warn ".env created from .env.example — update DATABASE_URL and SECRET_KEY before running"
fi

deactivate

# ─── Frontend setup ───────────────────────────────────────────────────────────

info "Setting up frontend..."

cd "$PROJECT_ROOT/frontend"

info "Installing Node.js dependencies..."
npm ci --silent
info "Frontend dependencies installed ✓"

if [ ! -f ".env.local" ]; then
    cp .env.example .env.local 2>/dev/null || warn ".env.example not found in frontend/"
fi

# ─── Done ─────────────────────────────────────────────────────────────────────

echo ""
info "Setup complete! Next steps:"
echo "  1. Edit backend/.env — set DATABASE_URL and SECRET_KEY"
echo "  2. Run migrations: cd backend && source venv/bin/activate && alembic upgrade head"
echo "  3. Start backend: cd backend && uvicorn src.main:app --reload"
echo "  4. Start frontend: cd frontend && npm run dev"
