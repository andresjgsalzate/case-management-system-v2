#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  hosts-setup.sh — Add `127.0.0.1 cms.local` to the OS hosts file.
#  Idempotent (re-running won't duplicate the entry).
#  Cross-platform: Linux, macOS, Windows (Git Bash / MSYS2 / Cygwin).
#
#  Required for the nginx reverse proxy (sub-spec 09): the browser
#  reaches Keycloak + n8n + CMS under one origin `cms.local`, which
#  must resolve to 127.0.0.1 where nginx listens (443).
#
#  Usage:
#    Linux/macOS:  sudo bash dev/hosts-setup.sh
#    Win Git Bash: run terminal "as administrator", then  bash dev/hosts-setup.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

HOST_LINE="127.0.0.1 cms.local"

detect_hosts_path() {
  case "$(uname -s)" in
    Linux*|Darwin*)
      echo "/etc/hosts"
      ;;
    MINGW*|MSYS*|CYGWIN*)
      # Git Bash exposes the Windows hosts file at /c/Windows/...
      echo "/c/Windows/System32/drivers/etc/hosts"
      ;;
    *)
      echo ""
      ;;
  esac
}

HOSTS_FILE="$(detect_hosts_path)"
if [[ -z "$HOSTS_FILE" ]]; then
  echo "ERROR: Unsupported OS ($(uname -s)). Add '${HOST_LINE}' to your hosts file manually." >&2
  exit 1
fi

if [[ ! -f "$HOSTS_FILE" ]]; then
  echo "ERROR: Hosts file not found at: $HOSTS_FILE" >&2
  exit 1
fi

# Idempotency: bail early if cms.local already resolves locally.
# `grep -E` matches both "127.0.0.1 cms.local" and "127.0.0.1\tcms.local"
# (some installers use tabs).
if grep -E "^[[:space:]]*127\.0\.0\.1[[:space:]]+cms\.local([[:space:]]|$)" "$HOSTS_FILE" >/dev/null 2>&1; then
  echo "OK: 'cms.local' already mapped in $HOSTS_FILE"
  exit 0
fi

# Append. Permissions: on Linux/macOS sudo is required; on Windows the
# shell needs to be elevated. We don't try to escalate ourselves — the
# script just fails clearly if we can't write.
if ! echo "$HOST_LINE" >> "$HOSTS_FILE" 2>/dev/null; then
  echo "ERROR: Cannot write to $HOSTS_FILE — re-run with elevated privileges." >&2
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      echo "  Windows: right-click Git Bash → 'Run as administrator', then re-run." >&2
      ;;
    *)
      echo "  Linux/macOS: prefix with sudo, e.g.  sudo bash dev/hosts-setup.sh" >&2
      ;;
  esac
  exit 1
fi

echo "OK: appended '${HOST_LINE}' to ${HOSTS_FILE}"
