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
  local exit_code=$?
  local line=$1
  local cmd=$2
  echo ""
  echo -e "${RED}══════════════════════════════════════${NC}"
  echo -e "${RED}  ERROR en línea $line (exit $exit_code)${NC}"
  echo -e "${RED}  Comando: ${cmd}${NC}"
  echo -e "${RED}  Revisa el mensaje de arriba.${NC}"
  echo -e "${RED}══════════════════════════════════════${NC}"
  echo ""
}
trap 'on_error $LINENO "$BASH_COMMAND"' ERR

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
head_ "1/6  Verificando herramientas"

command -v docker  >/dev/null 2>&1 || err "docker no encontrado"
command -v python  >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1 || err "python no encontrado"
command -v node    >/dev/null 2>&1 || err "node no encontrado"
command -v npm     >/dev/null 2>&1 || err "npm no encontrado"

PYTHON=$(command -v python3 2>/dev/null || command -v python)
# Guardamos el Python del sistema ANTES de cualquier venv activate. La sección
# 3 modificará $PYTHON para apuntar al venv del backend, pero las herramientas
# globales (code-review-graph instalado con pip --user) viven en el system
# Python y necesitan invocarse desde ahí.
SYSTEM_PYTHON="$PYTHON"
log "Python: $($PYTHON --version)"
log "Node:   $(node --version)"

# ─────────────────────────────────────────────────────────────
# 1.1  Detección de sistema operativo
# ─────────────────────────────────────────────────────────────
# Detectamos el entorno una sola vez al inicio. Las secciones posteriores
# (kill-port, zombie killer, venv path) ya tienen branching ad-hoc; esta
# variable centraliza la decisión y permite mostrar al usuario qué entorno
# se detectó (útil cuando un bug solo ocurre en uno de los tres).
#
# Valores:
#   linux        — Linux nativo (Ubuntu, Debian, Arch, …)
#   macos        — macOS (Darwin)
#   win_gitbash  — Windows con Git Bash / MSYS2 (powershell.exe disponible)
#   wsl          — Windows Subsystem for Linux (uname -r contiene microsoft)
OS_KIND="unknown"
case "$(uname -s)" in
  Linux*)
    if grep -qi microsoft /proc/version 2>/dev/null; then
      OS_KIND="wsl"
    else
      OS_KIND="linux"
    fi
    ;;
  Darwin*)  OS_KIND="macos" ;;
  MINGW*|MSYS*|CYGWIN*)
    OS_KIND="win_gitbash"
    ;;
esac

# Fallback defensivo: si uname no clasificó pero powershell.exe está en PATH,
# asumimos Git Bash. Cubre el caso de uname devolviendo string raro.
if [[ "$OS_KIND" == "unknown" ]] && command -v powershell.exe >/dev/null 2>&1; then
  OS_KIND="win_gitbash"
fi

log "Entorno detectado: ${BLUE}${OS_KIND}${NC}"

# ─────────────────────────────────────────────────────────────
# 1.5  Matar procesos backend/frontend de runs previos
# ─────────────────────────────────────────────────────────────
# Cierres impuros (Ctrl+C interrumpido, TaskStop, reload roto) dejan workers
# uvicorn (multiprocessing.spawn) y procesos node next-dev huérfanos que
# siguen ocupando puertos 8000/3000-3002 con código viejo o conexiones DB
# rotas — el síntoma típico es un 500 silencioso en /auth/login después de
# editar .env. Limpiar antes de arrancar es más rápido que diagnosticar.
head_ "1.5/6  Limpieza de procesos previos"

_kill_port() {
  local port="$1"
  local pids=""
  case "$OS_KIND" in
    win_gitbash)
      # Windows: usa Get-NetTCPConnection — captura LISTEN incluso con padre muerto.
      # El `|| true` evita que pipefail + set -e maten el script cuando no hay
      # procesos escuchando (PowerShell puede devolver $LASTEXITCODE=1 en pipelines
      # vacíos a pesar de -ErrorAction SilentlyContinue).
      pids="$(powershell.exe -NoProfile -Command \
        "Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue \
         | Select-Object -ExpandProperty OwningProcess -Unique" 2>/dev/null | tr -d '\r' || true)"
      for pid in $pids; do
        [[ -z "$pid" || "$pid" == "0" ]] && continue
        powershell.exe -NoProfile -Command "Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue" 2>/dev/null || true
        log "  killed PID $pid on :$port"
      done
      ;;
    linux|macos|wsl)
      if command -v lsof >/dev/null 2>&1; then
        pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
        for pid in $pids; do
          kill -9 "$pid" 2>/dev/null && log "  killed PID $pid on :$port" || true
        done
      elif command -v fuser >/dev/null 2>&1; then
        # Fallback para distros sin lsof (algunos contenedores minimalistas)
        fuser -k -n tcp "$port" 2>/dev/null && log "  killed listeners on :$port" || true
      fi
      ;;
  esac
}

for p in 8000 3000 3001 3002; do _kill_port "$p"; done

# Matar zombies de multiprocessing.spawn con parent_pid muerto (Windows).
# uvicorn --reload spawns un worker child; si reloader muere, el worker
# queda con el socket FD heredado y sigue respondiendo.
if [[ "$OS_KIND" == "win_gitbash" ]]; then
  powershell.exe -NoProfile -Command "
    Get-CimInstance Win32_Process -Filter \"Name='python3.13.exe' OR Name='python.exe'\" |
      Where-Object { \$_.CommandLine -match 'multiprocessing.spawn.*parent_pid=(\d+)' } |
      ForEach-Object {
        \$ppid = [int]\$matches[1]
        if (-not (Get-Process -Id \$ppid -ErrorAction SilentlyContinue)) {
          Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue
          Write-Output \"  killed zombie uvicorn worker PID \$(\$_.ProcessId) (dead parent \$ppid)\"
        }
      }" 2>/dev/null | sed 's/^/[dev] /' || true
fi

sleep 1
log "Limpieza OK ✓"

# ─────────────────────────────────────────────────────────────
# 2. Docker (Postgres + Redis)
# ─────────────────────────────────────────────────────────────
head_ "2/6  Servicios Docker (Postgres + Redis)"

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
head_ "3/6  Dependencias Python"

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
head_ "4/6  Migraciones Alembic + Seed"

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
head_ "5/6  Dependencias Node"

cd "$FRONTEND"

# Detectar node_modules desactualizado: si package-lock.json es más reciente
# que el install marker, las deps locales están viejas (típicamente porque el
# dev pulleó un commit con nuevas deps pero olvidó npm install). El marker
# `.package-lock.json` lo crea npm dentro de node_modules al final del install.
NODE_INSTALL_MARKER="$FRONTEND/node_modules/.package-lock.json"

if [[ ! -d "node_modules" ]]; then
  log "Instalando dependencias Node…"
  npm install
elif [[ -f "$FRONTEND/package-lock.json" && ( ! -f "$NODE_INSTALL_MARKER" || "$FRONTEND/package-lock.json" -nt "$NODE_INSTALL_MARKER" ) ]]; then
  warn "package-lock.json más reciente que node_modules — sincronizando…"
  npm install
else
  log "node_modules sincronizado ✓"
fi

# ─────────────────────────────────────────────────────────────
# 6. Actualizar code-review-graph (no bloqueante)
# ─────────────────────────────────────────────────────────────
head_ "6/6  Indexando código con code-review-graph"

cd "$ROOT"

# Detectamos vía `python -m code_review_graph` en lugar del binario directo:
# en Windows, el script `code-review-graph.exe` vive en el Scripts/ de pip
# user-packages, que NO siempre está en PATH cuando dev.bat lanza Git Bash.
# Llamar como módulo Python siempre funciona si el paquete está instalado.
if $SYSTEM_PYTHON -m code_review_graph --version >/dev/null 2>&1; then
  log "Actualizando grafo (solo archivos cambiados)…"
  if $SYSTEM_PYTHON -m code_review_graph update 2>&1 | tail -5; then
    log "Grafo actualizado ✓"
  else
    warn "code-review-graph update devolvió error — continuando sin grafo"
  fi
else
  warn "code-review-graph no instalado en el Python del sistema"
  warn "  Instálalo con:  pip install --user code-review-graph"
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

# Esperar a que CUALQUIERA muera (no a ambos).
#
# Bug previo: `wait $A $B` espera a que *ambos* PIDs terminen y devuelve
# el exit code del último. Si Next.js (frontend) crasheaba silenciosamente
# por OOM/Turbopack, el shell se quedaba en `wait` esperando al backend,
# que seguía vivo logueando requests del browser. Resultado: el operador
# veía logs normales mientras el browser tiraba 502 Bad Gateway porque
# el upstream :3000 estaba muerto -- sin ningún aviso en consola.
#
# `wait -n` (bash 4.3+) retorna apenas el primer PID termina, junto con
# su exit code. Identificamos cuál murió por liveness probe del otro y
# damos un mensaje claro + hint específico. La trap EXIT (línea 52) se
# encarga de matar al sobreviviente.
set +e
wait -n "$BACKEND_PID" "$FRONTEND_PID"
DEAD_EXIT=$?
set -e

if kill -0 "$BACKEND_PID" 2>/dev/null; then
  DEAD_NAME="FRONTEND (npm run dev / Next.js)"
  HINT="Causas comunes: Turbopack OOM (cerrá otras apps; probar NODE_OPTIONS=--max-old-space-size=4096), node_modules corruptos, o puerto 3000 ocupado."
elif kill -0 "$FRONTEND_PID" 2>/dev/null; then
  DEAD_NAME="BACKEND (uvicorn)"
  HINT="Causas comunes: import error en Python, env var faltante en backend/.env, puerto 8000 ocupado, o DB inaccesible."
else
  DEAD_NAME="AMBOS (carrera)"
  HINT="Murieron casi al mismo tiempo. Buscá el primer error real más arriba en este log."
fi

echo ""
echo -e "${RED}══════════════════════════════════════════════════════${NC}"
echo -e "${RED}  ${DEAD_NAME} murió (exit ${DEAD_EXIT})${NC}"
echo -e "${RED}  ${HINT}${NC}"
echo -e "${RED}  Bajando el proceso sobreviviente…${NC}"
echo -e "${RED}══════════════════════════════════════════════════════${NC}"

exit "$DEAD_EXIT"
