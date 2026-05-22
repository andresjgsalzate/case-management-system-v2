# Infrastructure — Reverse Proxy + Keycloak + n8n SSO (dev)

Operator runbook for the local stack introduced by sub-spec 09 (n8n iframe
embed). This document describes the **dev** topology. Production hardening
notes live at the bottom.

---

## Topology

```
Browser
  │
  ▼
nginx  (cms_nginx, TLS on 443)                 — in docker
  ├── /              → host.docker.internal:3000   (Next.js, started by dev.sh)
  ├── /api/*         → host.docker.internal:8000   (FastAPI,  started by dev.sh)
  ├── /auth/*        → keycloak:8080               — in docker
  ├── /n8n/*         → oauth2-proxy:4180 → n8n:5678 — in docker
  └── /webhook/*     → n8n:5678                    — in docker (no auth, HMAC at app layer)
```

The frontend + backend deliberately stay **on the host** (orchestrated by
`dev.sh` / `dev.bat`) so hot-reload, breakpoints, and IDE integration keep
working. The reverse proxy reaches them via `host.docker.internal`, which
Docker Desktop maps to the host gateway automatically on Windows and macOS;
on Linux the nginx service declares `extra_hosts: ["host.docker.internal:host-gateway"]`.

Everything is reachable under a single origin (`https://cms.local/`), which is
what lets the n8n iframe share the browser session cookie without `SameSite=None`
cross-site contortions.

---

## Prerequisites

- **Docker Desktop** running (Win/macOS) or Docker Engine ≥ 24 (Linux).
- **Git Bash** on Windows (ships with `openssl` and `bash`).
- **Admin/sudo** on first run — needed to write the hosts file.
- Ports free on the host: **443**, **3000**, **8000**, **5678**.

---

## First-time setup

Run from the repo root.

```bash
# 1) Map cms.local → 127.0.0.1 in the OS hosts file.
#    Linux/macOS:
sudo bash dev/hosts-setup.sh
#    Windows: open Git Bash as Administrator, then:
bash dev/hosts-setup.sh

# 2) Generate a self-signed TLS cert for cms.local.
bash dev/generate-dev-certs.sh
# → nginx/certs/cms.local.{crt,key}   (.key is gitignored)

# 3) Copy env template and edit secrets.
cp .env.example .env
# Fill in KEYCLOAK_ADMIN_PASSWORD, OAUTH2_PROXY_CLIENT_SECRET,
# OAUTH2_PROXY_COOKIE_SECRET (32-char random) before first boot.

# 4) Bring up the infra stack.
docker compose up -d nginx keycloak oauth2-proxy n8n postgres redis

# 5) Start backend + frontend (separate terminal).
bash dev.sh        # or  dev.bat  on Windows
```

Then open <https://cms.local/>. The browser will warn about the self-signed
cert on first visit — see "Trusting the dev cert" below.

---

## Trusting the dev cert

The generator does **not** install the cert into your OS trust store.
That's a deliberate choice — we keep `openssl` as the only dependency.
Trust manually once per machine:

- **Windows**: `certmgr.msc` → `Trusted Root Certification Authorities` →
  `Certificates` → right-click → `All Tasks` → `Import…` → select
  `nginx/certs/cms.local.crt`.
- **macOS**: double-click `nginx/certs/cms.local.crt`, search it in
  Keychain Access, expand `Trust`, set "When using this certificate" to
  `Always Trust`.
- **Linux** (Debian/Ubuntu):
  ```bash
  sudo cp nginx/certs/cms.local.crt /usr/local/share/ca-certificates/cms.local.crt
  sudo update-ca-certificates
  ```

Firefox uses its own trust store — import the `.crt` via
`Settings → Privacy & Security → Certificates → View Certificates → Authorities`.

---

## Common operations

### Tail logs

```bash
docker compose logs -f nginx
docker compose logs -f keycloak
docker compose logs -f oauth2-proxy
docker compose logs -f n8n
```

### Rotate the cert

```bash
bash dev/generate-dev-certs.sh --force
docker compose restart nginx
```

### Reset the Keycloak realm

The realm import file at `keycloak/realm-export.json` is loaded only on
**first** boot. To replay it during dev, blow away the Keycloak volume:

```bash
docker compose stop keycloak
docker compose rm -f keycloak
docker volume rm case-management-system_keycloak_data
docker compose up -d keycloak
```

`up -d` re-imports the realm because the empty volume re-triggers the
`--import-realm` flag.

### Rotate oauth2-proxy cookie secret

The cookie secret must be 16, 24, or 32 bytes (raw or base64). Generate one:

```bash
openssl rand -base64 32
```

Paste into `.env` under `OAUTH2_PROXY_COOKIE_SECRET`, then:

```bash
docker compose restart oauth2-proxy
```

Active sessions are invalidated.

### Inspect the cert chain a browser sees

```bash
openssl s_client -showcerts -servername cms.local -connect cms.local:443 </dev/null
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ERR_CERT_AUTHORITY_INVALID` in browser | Cert not trusted by OS | Follow "Trusting the dev cert" above |
| `502 Bad Gateway` on `/api/*` | Backend not running on host:8000 | `bash dev.sh` in another terminal |
| `502 Bad Gateway` on `/` | Frontend not running on host:3000 | Same — `dev.sh` starts it |
| `/n8n/` redirects forever | oauth2-proxy ↔ Keycloak misconfigured | Check `OAUTH2_PROXY_CLIENT_SECRET` matches the realm export |
| WebSocket in n8n editor doesn't update live | nginx missing `Upgrade`/`Connection` headers in `/n8n/` block | See `nginx/conf.d/cms.conf` |
| `Keycloak` won't import realm | Volume already populated from a previous run | See "Reset the Keycloak realm" |

---

## Production checklist

Don't ship the dev configuration. Before deploying:

- **TLS**: replace self-signed certs with a CA-issued cert (Let's Encrypt
  via `certbot` or a managed cert from the cloud provider). Pin
  `ssl_protocols TLSv1.2 TLSv1.3;` and a modern cipher suite.
- **Keycloak**: switch from `start-dev --import-realm` to `start --optimized`,
  point at a managed PostgreSQL (not the embedded H2). Disable the bootstrap
  admin once a real admin user is created.
- **oauth2-proxy**: set `cookie_secure: true`, `cookie_samesite: lax`,
  short `cookie_expire` (≤ 8 h), rotate cookie secret on every deploy.
- **nginx**: enable HSTS with `max-age=63072000; includeSubDomains; preload`
  only once you control the apex domain; gate brotli/gzip by `Accept-Encoding`;
  log to a structured sink, not the container's stdout, for retention.
- **Secrets**: source from the cloud provider's secret manager (AWS SM,
  GCP Secret Manager, Vault). Do not commit `.env`. Rotate the Keycloak
  bootstrap password on first login.
- **Backups**: include Keycloak's database (realm, users, federated identities)
  in the same backup window as the CMS database.
- **Networking**: put nginx behind a load balancer that terminates TLS, then
  re-encrypts to the container — or run nginx with HTTP only inside a
  private network and terminate TLS at the LB.

---

## Related docs

- `docs/superpowers/specs/2026-05-19-n8n-iframe-embed-design.md` — full design.
- `docs/superpowers/plans/2026-05-19-n8n-iframe-embed.md` — phased plan.
- `docs/COMPLIANCE.md` *(Phase 4)* — compensating-control documentation for SOC2 / ISO27001 while on n8n Community.
