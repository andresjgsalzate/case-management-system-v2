#!/usr/bin/env bash
# ============================================================
#  CMS Daily Backup Script
#  Backs up PostgreSQL database + uploads directory.
#  Retention: 30 days. Configure via environment or .env.backup
# ============================================================
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────
ENV_FILE="${ENV_FILE:-/opt/cms/.env.production}"
BACKUP_DIR="${BACKUP_DIR:-/var/lib/cms/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

DB_NAME="${DB_NAME:-cms_production}"
DB_USER="${DB_USER:-cms_user}"
UPLOADS_DIR="${UPLOADS_DIR:-/var/lib/cms/uploads}"
LOG_DIR="${LOG_DIR:-/var/log/cms}"

# ── Load production environment ───────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

# ── Helpers ───────────────────────────────────────────────────
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG="${LOG_DIR}/backup.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
die() { log "ERROR: $*"; exit 1; }

mkdir -p "$BACKUP_DIR"

# ── PostgreSQL dump ───────────────────────────────────────────
DB_BACKUP="${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz"
log "Starting PostgreSQL backup → ${DB_BACKUP}"

PGPASSWORD="${PGPASSWORD:-$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')}"
export PGPASSWORD

if pg_dump -U "$DB_USER" -h 127.0.0.1 "$DB_NAME" | gzip > "$DB_BACKUP"; then
    SIZE=$(du -sh "$DB_BACKUP" | cut -f1)
    log "Database backup OK (${SIZE})"
else
    die "pg_dump failed for database ${DB_NAME}"
fi

# ── Uploads directory ─────────────────────────────────────────
UPLOADS_BACKUP="${BACKUP_DIR}/uploads_${TIMESTAMP}.tar.gz"
if [[ -d "$UPLOADS_DIR" ]]; then
    log "Backing up uploads → ${UPLOADS_BACKUP}"
    tar -czf "$UPLOADS_BACKUP" -C "$(dirname "$UPLOADS_DIR")" "$(basename "$UPLOADS_DIR")"
    SIZE=$(du -sh "$UPLOADS_BACKUP" | cut -f1)
    log "Uploads backup OK (${SIZE})"
else
    log "No uploads directory at ${UPLOADS_DIR} — skipping"
fi

# ── Cleanup old backups ───────────────────────────────────────
log "Removing backups older than ${RETENTION_DAYS} days…"
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete
find "$BACKUP_DIR" -name "uploads_*.tar.gz" -mtime "+${RETENTION_DAYS}" -delete

REMAINING=$(find "$BACKUP_DIR" -name "*.gz" | wc -l)
log "Backup complete. ${REMAINING} archive(s) in ${BACKUP_DIR}"
