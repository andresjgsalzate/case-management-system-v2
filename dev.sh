#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  dev.sh — Arrancar todo el sistema de gestión de casos
#  Uso: bash dev.sh [--fresh]   (--fresh borra y re-seed la BD)
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

FRESH=false
if [[ "${1:-}" == "--fresh" ]]; then FRESH=true; fi

# ── Colores ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BLUE='\033[0;34m'; NC='\033[0m'

log()  { echo -e "${GREEN}[dev]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*"; exit 1; }
head_() { echo -e "\n${CYAN}══════════════════════════════════════${NC}"; echo -e "${CYAN}  $*${NC}"; echo -e "${CYAN}══════════════════════════════════════${NC}"; }

# ── Handler de errores inesperados ────────────────────────────
on_error() {
  local line=$1
  echo ""
  echo -e "${RED}══════════════════════════════════════${NC}"
  echo -e "${RED}  ERROR en línea $line${NC}"
  echo -e "${RED}  Revisa el mensaje de arriba.${NC}"
  echo -e "${RED}══════════════════════════════════════${NC}"
  echo ""
}
trap 'on_error $LINENO' ERR

# ── Limpieza al salir (Ctrl+C o fin normal) ───────────────────
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  warn "Deteniendo procesos…"
  [[ -n "$BACKEND_PID" ]]  && kill "$BACKEND_PID"  2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  [[ -n "$BACKEND_PID" ]]  && wait "$BACKEND_PID"  2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && wait "$FRONTEND_PID" 2>/dev/null || true
  log "Todo detenido. ¡Hasta luego!"
}
trap cleanup SIGINT SIGTERM EXIT

# ─────────────────────────────────────────────────────────────
# 1. Verificar herramientas
# ─────────────────────────────────────────────────────────────
head_ "1/5  Verificando herramientas"

command -v docker  >/dev/null 2>&1 || err "docker no encontrado"
command -v python  >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1 || err "python no encontrado"
command -v node    >/dev/null 2>&1 || err "node no encontrado"
command -v npm     >/dev/null 2>&1 || err "npm no encontrado"

PYTHON=$(command -v python3 2>/dev/null || command -v python)
log "Python: $($PYTHON --version)"
log "Node:   $(node --version)"

# ─────────────────────────────────────────────────────────────
# 2. Docker (Postgres + Redis)
# ─────────────────────────────────────────────────────────────
head_ "2/5  Servicios Docker (Postgres + Redis)"

cd "$ROOT"

if $FRESH; then
  warn "--fresh: eliminando volúmenes de base de datos…"
  docker compose down -v --remove-orphans 2>/dev/null || true
fi

docker compose up -d

# Esperar que Postgres esté listo
log "Esperando Postgres…"
until docker compose exec -T postgres pg_isready -U cms_user -d cms_dev -q 2>/dev/null; do
  echo -n "."
  sleep 1
done
echo ""
log "Postgres listo ✓"

# Esperar que Redis esté listo
log "Esperando Redis…"
until docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; do
  echo -n "."
  sleep 1
done
echo ""
log "Redis listo ✓"

# ─────────────────────────────────────────────────────────────
# 3. Dependencias Python
# ─────────────────────────────────────────────────────────────
head_ "3/5  Dependencias Python"

cd "$BACKEND"

VENV="$BACKEND/venv"

# Estrategia: usar el venv existente si ya tiene uvicorn,
# si no intenta activarlo/instalarlo, y como último recurso
# usa el Python del sistema (donde ya estaban instalados los paquetes).
_activate_venv() {
  if [[ -f "$VENV/Scripts/activate" ]]; then
    source "$VENV/Scripts/activate"
  else
    source "$VENV/bin/activate"
  fi
}

_has_uvicorn() {
  python -c "import uvicorn" 2>/dev/null
}

if [[ -d "$VENV" ]]; then
  log "Venv encontrado en $VENV — activando…"
  _activate_venv
  if _has_uvicorn; then
    log "Paquetes OK (uvicorn disponible) ✓"
  else
    warn "Venv incompleto — intentando instalar dependencias…"
    pip install -q -r requirements.txt 2>&1 || {
      warn "pip install falló en el venv. Usando Python del sistema."
      deactivate 2>/dev/null || true
      PYTHON=$(command -v python3 2>/dev/null || command -v python)
    }
  fi
else
  # Sin venv: verificar si el Python del sistema tiene los paquetes
  if _has_uvicorn 2>/dev/null || $PYTHON -c "import uvicorn" 2>/dev/null; then
    log "Paquetes encontrados en Python del sistema ✓"
  else
    warn "Creando venv e instalando dependencias…"
    $PYTHON -m venv "$VENV"
    _activate_venv
    pip install -q -r requirements.txt
  fi
fi

# Asegurar que PYTHON apunta al ejecutable activo
PYTHON=$(command -v python)

# ─────────────────────────────────────────────────────────────
# 4. Migraciones + Seed  (no bloquean el arranque si fallan)
# ─────────────────────────────────────────────────────────────
head_ "4/5  Migraciones Alembic + Seed"

cd "$BACKEND"

log "Ejecutando migraciones…"
if $PYTHON -m alembic upgrade head 2>&1; then
  log "Migraciones OK ✓"
else
  warn "Migraciones fallaron o ya están al día — continuando de todas formas"
fi

cd "$ROOT"
log "Ejecutando seed…"
if $PYTHON -m scripts.seed 2>&1; then
  log "Seed OK ✓"
else
  warn "Seed falló o ya estaba cargado — continuando de todas formas"
fi

# ─────────────────────────────────────────────────────────────
# 5. Dependencias Node
# ─────────────────────────────────────────────────────────────
head_ "5/5  Dependencias Node"

cd "$FRONTEND"

if [[ ! -d "node_modules" ]]; then
  log "Instalando dependencias Node…"
  npm install
else
  log "node_modules OK ✓"
fi

# ─────────────────────────────────────────────────────────────
# Arrancar Backend y Frontend en paralelo
# ─────────────────────────────────────────────────────────────
head_ "Arrancando Backend + Frontend"

cd "$ROOT"

log "Iniciando backend  → http://localhost:8000"
log "Iniciando frontend → http://localhost:3000"
log "API Docs           → http://localhost:8000/docs"
echo ""
warn "Presiona Ctrl+C para detener todo"
echo ""

(
  if [[ -f "$VENV/Scripts/activate" ]]; then
    source "$VENV/Scripts/activate"
  fi
  export PYTHONPATH="$ROOT"
  cd "$BACKEND"
  $PYTHON -m uvicorn backend.src.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload 2>&1
) &
BACKEND_PID=$!

sleep 2

(
  cd "$FRONTEND"
  npm run dev 2>&1
) &
FRONTEND_PID=$!

# Esperar a que ambos procesos terminen
wait "$BACKEND_PID" "$FRONTEND_PID"
