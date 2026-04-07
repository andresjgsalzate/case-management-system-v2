#!/usr/bin/env bash
# Installs the CMS nginx configuration.
# Usage: sudo bash configure-nginx.sh [domain]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOMAIN="${1:-}"

[[ $EUID -eq 0 ]] || { echo "Run as root"; exit 1; }

# ── Prompt for domain if not provided ────────────────────────
if [[ -z "$DOMAIN" ]]; then
    read -rp "Enter your domain (e.g. cms.example.com): " DOMAIN
fi
[[ -n "$DOMAIN" ]] || { echo "Domain is required"; exit 1; }

# ── Install config ────────────────────────────────────────────
NGINX_CONF="/etc/nginx/sites-available/cms"
cp "${SCRIPT_DIR}/nginx.conf" "$NGINX_CONF"
sed -i "s/DOMAIN_PLACEHOLDER/${DOMAIN}/g" "$NGINX_CONF"

# ── Enable site ───────────────────────────────────────────────
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/cms
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

# ── Syntax check ─────────────────────────────────────────────
nginx -t || { echo "Nginx config test failed — check ${NGINX_CONF}"; exit 1; }

# ── Reload ────────────────────────────────────────────────────
systemctl reload nginx
echo "Nginx configured for ${DOMAIN}"
echo ""
echo "Next step — obtain SSL certificate:"
echo "  sudo certbot --nginx -d ${DOMAIN}"
