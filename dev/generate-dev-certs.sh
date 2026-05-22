#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  generate-dev-certs.sh — Create a self-signed TLS cert for cms.local.
#
#  Uses OpenSSL (ships with Git Bash on Windows, default on Linux/macOS).
#  No mkcert dependency. The cert is NOT trusted by the OS by default —
#  the first time you visit https://cms.local the browser will warn;
#  follow the "trust manually" steps in docs/INFRA.md.
#
#  Output:
#    nginx/certs/cms.local.crt
#    nginx/certs/cms.local.key
#
#  Idempotent: re-running overwrites only if --force is passed.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="$ROOT/nginx/certs"
CRT="$CERT_DIR/cms.local.crt"
KEY="$CERT_DIR/cms.local.key"

FORCE=false
[[ "${1:-}" == "--force" ]] && FORCE=true

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl not found in PATH." >&2
  echo "  Git Bash includes it; on bare cmd.exe install Git for Windows." >&2
  exit 1
fi

mkdir -p "$CERT_DIR"

if [[ -f "$CRT" && -f "$KEY" && "$FORCE" == "false" ]]; then
  # Verify expiry: regenerate if cert expires within 7 days.
  if openssl x509 -checkend 604800 -noout -in "$CRT" >/dev/null 2>&1; then
    echo "OK: cert already valid at ${CRT} (use --force to regenerate)."
    exit 0
  fi
  echo "Cert expires within 7 days — regenerating."
fi

# SAN config — modern browsers reject certs without subjectAltName.
# Single-file config keeps everything together; no openssl.cnf required.
SAN_CONFIG="$(mktemp -t cms-san-XXXX.cnf)"
trap 'rm -f "$SAN_CONFIG"' EXIT

cat > "$SAN_CONFIG" <<'EOF'
[req]
distinguished_name = req_distinguished_name
prompt             = no
x509_extensions    = v3_ca

[req_distinguished_name]
CN = cms.local
O  = CMS Dev (self-signed)

[v3_ca]
subjectAltName       = @alt
basicConstraints     = critical,CA:FALSE
keyUsage             = critical,digitalSignature,keyEncipherment
extendedKeyUsage     = serverAuth

[alt]
DNS.1 = cms.local
DNS.2 = *.cms.local
DNS.3 = localhost
IP.1  = 127.0.0.1
EOF

# 825 days is the macOS/iOS cap for self-signed certs.
openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout "$KEY" \
  -out    "$CRT" \
  -config "$SAN_CONFIG" >/dev/null 2>&1

chmod 600 "$KEY" 2>/dev/null || true

echo "OK: wrote $CRT (and matching key)"
echo "    Fingerprint: $(openssl x509 -noout -fingerprint -sha256 -in "$CRT" | sed 's/^.*=//')"
echo ""
echo "Trust manually so the browser stops warning:"
echo "  Windows : Import .crt into 'Trusted Root Certification Authorities' (certmgr.msc)."
echo "  macOS   : Open the .crt in Keychain → set 'Always Trust'."
echo "  Linux   : sudo cp ${CRT} /usr/local/share/ca-certificates/cms.local.crt && sudo update-ca-certificates"
