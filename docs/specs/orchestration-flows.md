# Orquestación CMS ↔ n8n ↔ Python — contrato de flujos

Guía de referencia para construir workflows que combinan el CMS (system of
record), n8n (director de orquesta) y microservicios Python (los músicos:
clientes de API + lógica pesada), entre Wazuh (EDR/SIEM), threat-intel
(VirusTotal / AlienVault) y Velociraptor (forense).

> **Estado**: documento de contrato. Marca qué endpoints YA EXISTEN vs los
> que faltan construir. Es la spec para los microservicios nuevos y la guía
> para que cualquiera arme workflows n8n sin reverse-engineer el código.

---

## 1. División de responsabilidades

| Capa | Rol | Hace | NO hace |
|---|---|---|---|
| **CMS (Python/FastAPI)** | System of record | Estado del caso, RBAC, audit, emite eventos de ciclo de vida, recibe enriquecimiento/evidencia | Lógica de orquestación multi-paso |
| **n8n** | Director de orquesta | Secuencia llamadas HTTP, rutea a Slack/Teams, ata fases | Decisiones de seguridad, persistencia autoritativa |
| **Microservicios Python** | Músicos | Clientes de API externas (VT, OTX, Wazuh, Velociraptor), normalización, queries paralelas | Mantener estado (lo delega al CMS) |

**Regla de oro**: la **decisión** y el **estado** viven en CMS. n8n **secuencia**.
Python **ejecuta** las llamadas pesadas. Si un workflow n8n desaparece, el CMS
sigue siendo la fuente de verdad.

**Patrón de disparo: PUSH, no poll.** El CMS empuja a n8n vía la acción
`trigger_n8n_workflow` del AutomationEngine cuando ocurre un evento de ciclo
de vida. n8n NO debe pollear la API del CMS.

---

## 2. Endpoints — estado actual

| Endpoint | Método | Propósito | Estado |
|---|---|---|---|
| `/api/v1/integrations/sources/{source_id}/events` | POST | Webhook inbound (Wazuh → CMS). Auth HMAC por source. | ✅ existe |
| `/api/v1/cases/{case_id}/triage` | POST/GET | Triage estructurado | ✅ existe |
| `/api/v1/cases/{case_id}/notes` | POST | Nota interna (comentario) | ✅ existe |
| `/api/v1/cases/{case_id}/attachments` | POST | Subir evidencia | ✅ existe |
| `/api/v1/cases/{case_id}/transition` | POST | Cambiar estado del caso | ✅ existe |
| `/api/v1/forensic/cases/{case_id}/hunts` | POST | Lanzar hunt Velociraptor (RO; destructivos vía n8n bridge) | ✅ existe |
| AutomationEngine action `trigger_n8n_workflow` | — | CMS → n8n push en eventos | ✅ existe |
| n8n callback (`n8n_bridge.handle_callback`, JWT) | — | n8n → CMS resultado | ✅ existe |
| **`/api/v1/enrichment/reputation`** | POST | VirusTotal + AlienVault (queries paralelas) | ❌ **a construir** |
| **`/api/v1/wazuh/syscheck`** | GET | Query outbound a Wazuh (movimiento lateral por hash) | ❌ **a construir** |
| **`/api/v1/cases/{case_id}/custom-values`** | PUT | Escribir campos custom (hosts comprometidos) | ⚠️ verificar/completar |

**Eventos de ciclo de vida que el CMS emite** (`AutomationEngine` los escucha):
`case.created`, `case.status_changed`, `case.assigned`, `case.closed`. Una
regla en `/settings/automation` con `trigger_event = case.status_changed` +
condición `to_status = "<estado>"` + acción `trigger_n8n_workflow` dispara n8n
en cualquier transición — sin código nuevo.

---

## 3. Flujo de referencia (4 fases)

### Fase 1 — Detección e Ingesta (Wazuh → CMS)

```
Wazuh (EDR/SIEM) detecta anomalía
   │ webhook HMAC
   ▼
POST /api/v1/integrations/sources/{source_id}/events
   │ (integrations.process_event: normaliza + resuelve taxonomía + crea caso)
   ▼
CMS crea caso "Abierto - Pendiente de Triaje", asigna cola SOC
   └─► emite evento case.created
```

- **Quién**: Wazuh → CMS (directo, sin n8n)
- **Auth**: HMAC por `integration_source` (ya configurado)
- **Payload inbound**: JSON crudo de Wazuh; el parser del source lo normaliza
  (hash, IPs, hostname, severidad). Ver `integrations/application/parsers/`.
- **Salida**: `case_id` + caso en estado inicial.
- **Estado**: ✅ funcional hoy.

> Nota: tu visión menciona "API de Ingesta en Python" separada. En el CMS
> esa función YA la cumple `integrations.process_event`. No hace falta un
> servicio aparte salvo que quieras desacoplar la normalización pesada — en
> ese caso, un parser custom en `integrations/application/parsers/` es el
> lugar correcto, no un microservicio nuevo.

### Fase 2 — Enriquecimiento y Notificación SOC

```
CMS emite case.created
   │ AutomationEngine rule (trigger_event=case.created) → trigger_n8n_workflow
   ▼
n8n recibe el push con { case_id, iocs, ... }
   │
   ├─► POST /api/v1/enrichment/reputation   { hashes:[...], ips:[...] }   ❌ a construir
   │      Python: asyncio.gather sobre VirusTotal /files/{hash}
   │              + AlienVault OTX. Devuelve veredicto consolidado.
   │      ◄── { "<hash>": {"vt":"15/70","otx":"malicious"}, ... }
   │
   ├─► POST /api/v1/cases/{case_id}/notes   { body: "<reporte reputación>", internal: true }   ✅
   │
   └─► n8n nodo Slack/Teams → notifica analista de turno   (nodo nativo n8n, cero código)
```

- **Quién**: CMS → n8n → (enrichment Python + CMS notes + Slack)
- **A construir**: microservicio `enrichment`.
  - `POST /api/v1/enrichment/reputation`
  - Body: `{ "hashes": ["sha256..."], "ips": ["1.2.3.4"] }`
  - Lee `VT_API_KEY` + `OTX_API_KEY` de `backend/.env`
  - Queries paralelas (`asyncio.gather`), timeout + manejo de rate-limit
  - Respuesta: `{ "hashes": { "<h>": {"vt_detections":"15/70","vt_link":"...","otx_pulses":3} }, "ips": {...} }`
- **Estado**: notes ✅, Slack ⚠️ (nodo n8n), enrichment ❌.

### Fase 3 — Triage y Revisión del Analista

```
Analista cambia estado → "En Revisión - Ejecutando Playbook"
   │ POST /api/v1/cases/{case_id}/transition
   │ → emite case.status_changed { to_status: "En Revisión..." }
   │ AutomationEngine rule (condición to_status) → trigger_n8n_workflow
   ▼
n8n playbook de validación
   │
   ├─► GET /api/v1/wazuh/syscheck?hash=<h>   ❌ a construir
   │      Python: wrapper sobre Wazuh REST API /syscheck/
   │      ◄── [ {host:"srv-02", path:"..."}, {host:"srv-07"} ]   (movimiento lateral)
   │
   └─► PUT /api/v1/cases/{case_id}/custom-values   ⚠️ verificar
          { "compromised_hosts": ["srv-02","srv-07"] }
```

- **Quién**: Analista → CMS (transición) → n8n → (Wazuh query Python + CMS custom-values)
- **A construir**:
  - Cliente Wazuh outbound (`wazuh_query` o extensión de `integrations`):
    `GET /api/v1/wazuh/syscheck?hash=<sha256>` → lista de hosts con ese hash.
    Wrapper sobre Wazuh Manager REST API (auth + paginado + parsing).
  - Update de custom values del caso (verificar si `service_catalog` custom
    values ya expone un PUT; si no, completar).
- **Estado**: transición + evento ✅, Wazuh query ❌, custom-values ⚠️.

### Fase 4 — Auditoría Forense (Velociraptor)

```
Analista cambia etiqueta → "Iniciar Auditoría Forense"
   │ (transición o label change) → emite evento → trigger_n8n_workflow
   ▼
n8n → Velociraptor playbook
   │
   ├─► (vía n8n bridge approval si es destructivo)
   │   POST /api/v1/forensic/cases/{case_id}/hunts   { artifact: "Windows.KapeFiles.Targets", host: "srv-02" }   ✅
   │      Python forensic.launch_hunt → Velociraptor gRPC → crea Hunt
   │
   │   Velociraptor ejecuta → genera evidencia (.jsonl/.zip)
   │   forensic.callback_handler recibe la notificación de fin   ✅
   │
   ├─► POST /api/v1/cases/{case_id}/attachments   (sube resumen de artefactos)   ✅
   │
   └─► POST /api/v1/cases/{case_id}/transition   → "Forense Completado - Pendiente de Mitigación"   ✅
```

- **Quién**: Analista → CMS → n8n → (Velociraptor Python gRPC + CMS attachments + transición)
- **A construir**: nada nuevo de capacidad — todo existe. Solo orquestar desde n8n.
- **Gobernanza**: hunts destructivos pasan por el approval flow
  (`n8n_bridge` / permisos CMS), nunca el path directo. Ver comentario en
  `forensic/application/use_cases.py`.
- **Estado**: ✅ todas las piezas existen.

---

## 4. Resumen: qué falta construir

| # | Pieza | Módulo | Esfuerzo | Necesita |
|---|---|---|---|---|
| 1 | Microservicio enriquecimiento (VT + OTX) | `enrichment/` (nuevo) | ~250 líneas | `VT_API_KEY`, `OTX_API_KEY` en .env |
| 2 | Cliente Wazuh outbound (`/syscheck`) | `wazuh_query/` (nuevo) o extender `integrations/` | ~150 líneas | URL + credenciales Wazuh Manager API |
| 3 | Update de custom values (PUT) | `service_catalog/` o `cases/` | verificar primero | — |

Velociraptor, notes, attachments, transición, eventos de ciclo de vida,
`trigger_n8n_workflow` y el callback de n8n **ya existen**.

---

## 5. Cómo se arma un workflow n8n nuevo (receta)

1. **Disparo**: en CMS, `/settings/automation` → regla nueva:
   - `trigger_event`: `case.created` | `case.status_changed` | `case.assigned`
   - condición (opcional): `to_status = "<estado>"` o `service_catalog_item_id = "<id>"`
   - acción: `trigger_n8n_workflow` con el `workflow_id` del catálogo + params
2. **En n8n**: webhook node recibe el payload del CMS (incluye `case_id`,
   `callback_url`, `callback_jwt`).
3. **Secuenciar**: nodos HTTP Request a los microservicios Python + APIs CMS.
   Usar `callback_jwt` en el header `Authorization: Bearer` para escribir de
   vuelta al CMS.
4. **Notificar**: nodo Slack/Teams nativo de n8n al final.
5. **Cerrar el loop**: opcional, POST al `callback_url` para que el CMS marque
   el `PlaybookRun` como completado (audit).

**Seguridad**: el `callback_jwt` es corto-vivido (~5 min) y firmado. Cualquier
escritura de n8n al CMS lo usa. Los workflows n8n son "recetas de
secuenciación" sobre APIs bien definidas — no toman decisiones de seguridad
(esas viven en CMS con RBAC real).

---

## 6. Gobernanza y RBAC (Python como guardián)

> Decisión arquitectónica formal en **ADR 0001**
> (`docs/adr/0001-python-rbac-gateway.md`). Esta sección es la guía práctica.

**Principio**: toda acción crítica se valida en Python (CMS), no en n8n.
n8n transporta datos + secuencia; **no decide permisos**.

### 6.1 Capas de control

```
Analista (en CMS) ──► CMS API (PermissionChecker) ──► evento ──► n8n
                          │ 403 si no autorizado              │
                          ▼                                    ▼
                    decisión + estado              n8n lleva approval_request_id
                    (audit inmutable)                          │
                                                               ▼
                                      Python valida approval contra DB
                                      (_enforce_destructive_governance)
                                               │ 403 si no aprobado
                                               ▼
                                      Velociraptor / Wazuh
                                      (keys SOLO en contenedor Python)
```

### 6.2 Niveles SOC → capacidades

El CMS usa permisos por **capacidad** (`resource:action`), no tiers rígidos.
Los niveles son bundles:

| Nivel | Capacidades |
|---|---|
| **L1** | `cases:read`, `cases:update`, `forensic:read`, `forensic:launch_ro` |
| **L2 / Forense** | L1 + `forensic:launch_destructive`, `forensic:cancel_own` |
| **Admin SOC** | L2 + `security_taxonomies:manage_global`, `integrations:manage` |

### 6.3 Gate de acción destructiva (ya implementado)

`forensic._enforce_destructive_governance` exige TODO esto o tira `403`:
- `n8n_run_id` presente (no hay path directo desde UI)
- `approval_request_id` que resuelve a un `ApprovalRequest`
- approval en estado `'approved'`
- `case_id` del approval coincide con el del hunt

Traducción a tu "Paso C": un L1 que presiona "Lanzar Velociraptor" sobre un
artefacto destructivo es rechazado por Python (403) — n8n nunca toca
Velociraptor. Un L2 con approval aprobado + caso en estado correcto pasa.

### 6.4 Aislamiento de secretos

| Secreto | Vive en | n8n lo ve? |
|---|---|---|
| Velociraptor mTLS (`api.config.yaml`) | contenedor backend | ❌ |
| Wazuh HMAC (por `integration_source`) | backend DB (cifrado) | ❌ |
| VT/OTX API keys (futuro enrichment) | `backend/.env` | ❌ |
| callback_jwt (corto-vivido) | emitido por CMS, usado por n8n | ✅ (es el único token que toca) |

### 6.5 Brechas de enforcement pendientes

La arquitectura está; faltan estas tuercas (ninguna es rediseño):

| # | Brecha | Esfuerzo |
|---|---|---|
| 1 | Justificación técnica **obligatoria** en solicitud destructiva | ~15 líneas |
| 2 | Nota **bloqueada** (no editable) de auditoría en el caso | ~30 líneas |
| 3 | **Alerta automática** en ticket al denegar acción no autorizada | ~25 líneas |
| 4 | Seed de **roles L1/L2/Forense** (bundles de capacidades) | seed |
| 5 (opc) | Token **single-use** para invocación Velociraptor | ~40 líneas |

---

## 7. Origen de este documento

Capturado en sesión de diseño 2026-05-24 a partir del escenario de referencia
de 4 fases (Wazuh → enriquecimiento → triage → forense). Decisión arquitectónica:
**Python + n8n combinados** — n8n orquesta, Python ejecuta, CMS es system of
record. Ver el VS que precedió esta decisión en el historial de la sesión;
formalizar como ADR si se requiere para auditoría.
