#!/usr/bin/env bash
# Registers and starts CMS systemd services.
# Run as root after setup.sh or independently.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ $EUID -eq 0 ]] || { echo "Run as root"; exit 1; }

install_service() {
    local name="$1"
    local src="${SCRIPT_DIR}/${2}"
    local dest="/etc/systemd/system/${name}.service"

    cp "$src" "$dest"
    chmod 644 "$dest"
    echo "Installed ${dest}"
}

install_service "cms-backend"  "backend.service"
install_service "cms-frontend" "frontend.service"

systemctl daemon-reload

systemctl enable cms-backend
systemctl enable cms-frontend

systemctl restart cms-backend
systemctl restart cms-frontend

echo ""
echo "Service status:"
systemctl is-active cms-backend  && echo "  cms-backend:  active" || echo "  cms-backend:  FAILED"
systemctl is-active cms-frontend && echo "  cms-frontend: active" || echo "  cms-frontend: FAILED"
echo ""
echo "Logs: journalctl -u cms-backend -u cms-frontend -f"
