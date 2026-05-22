#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  smoke-test.sh — sub-spec 09 Phase 1 acceptance probe.
#
#  Run after `docker compose up -d nginx keycloak oauth2-proxy n8n`
#  AND `dev.sh` (frontend + backend on host). Verifies the reverse
#  proxy stitches everything under https://cms.local correctly.
#
#  Exit codes:
#    0  — all checks passed
#    1  — at least one check failed (script prints which)
# ─────────────────────────────────────────────────────────────
set -u

BASE="https://cms.local"
CURL_OPTS=(--silent --show-error --insecure --max-time 10
           --output /dev/null --write-out "%{http_code}")
# `--insecure` is OK here — the cert is self-signed for dev. Production
# smoke tests should drop this flag.

FAILED=0
NL=$'\n'

check() {
  local name="$1" url="$2" expect_re="$3"
  local got
  got=$(curl "${CURL_OPTS[@]}" "$url" 2>/dev/null || echo "000")
  if [[ "$got" =~ $expect_re ]]; then
    printf '  \033[32mOK\033[0m   %-50s → %s\n' "$name" "$got"
  else
    printf '  \033[31mFAIL\033[0m %-50s → %s (expected %s)\n' "$name" "$got" "$expect_re"
    FAILED=$((FAILED + 1))
  fi
}

echo "Probing $BASE …"
echo

# Frontend (Next.js dev server on host:3000). Next returns 200 on '/'.
check "GET /                 (frontend)"          "$BASE/"                    '^(200|307|308)$'

# Backend (FastAPI). 401/403 is fine on a protected endpoint; the point
# is that nginx reached the backend — anything ≥ 200 < 500 proves the hop.
check "GET /api/health       (backend reach)"    "$BASE/api/health"          '^(200|401|403|404)$'

# Keycloak well-known endpoint — returns JSON OIDC discovery doc.
check "GET /auth/realms/cms/.well-known/openid-configuration" \
      "$BASE/auth/realms/cms/.well-known/openid-configuration"               '^200$'

# n8n editor via oauth2-proxy. Unauthenticated → redirect to Keycloak (302).
check "GET /n8n/             (oauth2-proxy gate)" "$BASE/n8n/"                '^(302|303|307)$'

# CSP frame-ancestors header — required so the /n8n iframe can embed.
echo
echo "CSP frame-ancestors:"
HEADERS=$(curl --silent --insecure --max-time 5 -I "$BASE/" 2>/dev/null || true)
if grep -qi "content-security-policy:.*frame-ancestors[[:space:]]*['\"]\\?self" <<<"$HEADERS"; then
  printf "  \033[32mOK\033[0m   CSP includes frame-ancestors 'self'\n"
else
  printf "  \033[31mFAIL\033[0m CSP header missing 'frame-ancestors self'\n"
  echo "${NL}Full headers:"
  printf '%s\n' "$HEADERS" | sed 's/^/    /'
  FAILED=$((FAILED + 1))
fi

echo
if [[ "$FAILED" -eq 0 ]]; then
  printf "\033[32mAll checks passed.\033[0m\n"
  exit 0
else
  printf "\033[31m%d check(s) failed.\033[0m\n" "$FAILED"
  exit 1
fi
