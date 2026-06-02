# ADR 0001 — Python como gateway central de RBAC y gobernanza

- **Estado**: Aceptado
- **Fecha**: 2026-05-24
- **Decisores**: Equipo CMS / SOC
- **Contexto técnico**: orquestación CMS ↔ n8n ↔ Python entre Wazuh,
  threat-intel y Velociraptor (ver `docs/specs/orchestration-flows.md`).

---

## Contexto

El sistema combina tres capas (decisión ya tomada, ver §Decisión de
`orchestration-flows.md`):

- **CMS (Python/FastAPI)** — system of record, estado, RBAC, audit.
- **n8n** — director de orquesta (secuencia llamadas HTTP, rutea a Slack).
- **Microservicios Python** — clientes de API pesadas (VirusTotal, AlienVault,
  Wazuh outbound, Velociraptor gRPC).

Las acciones que esta orquestación puede disparar incluyen operaciones
**destructivas e irreversibles sobre infraestructura corporativa**: aislar un
host en Wazuh, recolectar memoria volátil / clonar discos en Velociraptor,
lanzar hunts forenses. Estas acciones tienen requisitos de:

1. **Autorización** — solo roles habilitados (ej. analista forense L2), no
   cualquier analista L1.
2. **Trazabilidad / compliance** — quién, cuándo, por qué, con qué nivel de
   acceso, ligado a un caso de soporte. Auditoría inmutable.
3. **Aislamiento de secretos** — las API keys maestras de Wazuh/Velociraptor
   no deben estar al alcance de n8n ni del frontend.

El riesgo a evitar: que n8n (que NO tiene RBAC en su edición Community —
motivo por el cual existe el Workflow Change Request tracker como control
compensatorio SOC2) se convierta en el punto donde se decide qué puede
ejecutar quién. Si n8n decidiera permisos, un cambio no auditado de un
workflow podría escalar privilegios o ejecutar acciones destructivas sin
respaldo.

---

## Decisión

**Toda acción crítica se valida en Python (CMS), no en n8n.** Python es el
único "guardián":

1. **RBAC en el borde de la API CMS.** Cada endpoint sensible está protegido
   por `PermissionChecker(resource, action)`. n8n y el frontend solo pueden
   ejecutar lo que la API de Python les autorice; reciben `403 Forbidden`
   antes de que la petición toque a Wazuh/Velociraptor.

2. **n8n transporta, no decide.** Los workflows n8n son recetas de
   secuenciación sobre APIs bien definidas. Llevan el `approval_request_id` y
   el `case_id`, pero la validación de que ese approval esté aprobado +
   corresponda al caso ocurre en Python (`_enforce_destructive_governance`).
   n8n no puede "mentir" un permiso porque Python valida contra la DB.

3. **Acciones destructivas exigen el combo completo** (ya implementado en
   `forensic/application/use_cases.py:_enforce_destructive_governance`):
   - `n8n_run_id` presente (no hay path directo desde la UI),
   - `approval_request_id` que resuelve a un `ApprovalRequest`,
   - ese approval en estado `'approved'`,
   - el `case_id` del approval coincide con el del hunt.
   Si falta cualquiera → `PermissionDeniedError` (403).

4. **Secretos aislados en el contenedor Python.** Las credenciales de
   Velociraptor (mTLS vía `api.config.yaml`) y de Wazuh (HMAC por
   `integration_source`) viven solo en el backend. n8n y el frontend nunca
   las ven.

5. **CMS es la fuente de verdad de la auditoría.** Cada autorización/denegación
   queda registrada en `audit_logs` (append-only) y, como nota bloqueada en el
   caso, dejando "quién, cuándo, por qué, con qué nivel".

### Niveles de analista → capacidades

El CMS modela permisos por **capacidad atómica**, no por tier jerárquico. Los
"niveles" del SOC se definen como bundles de capacidades:

| Nivel SOC | Capacidades (resource:action) |
|---|---|
| Analista L1 | `cases:read`, `cases:update`, `forensic:read`, `forensic:launch_ro` (read-only) |
| Analista L2 / Forense | L1 + `approvals:approve`, `forensic:cancel_own` |
| Admin SOC | L2 + `security_taxonomies:manage_global`, `integrations:manage`, gestión de catálogos |

> **Nota sobre el gate destructivo**: no existe un permiso
> `forensic:launch_destructive`. La capacidad que separa L1 de L2 es
> `approvals:approve` (autorizar el `ApprovalRequest`), combinada con el
> routing obligatorio por n8n que valida `_enforce_destructive_governance`.
> Un L1 sin `approvals:approve` no puede autorizar hunts destructivos. El
> seed (`scripts/seed.py`) ya usa el permiso correcto.

Ventaja sobre tiers rígidos: se puede crear un "L1.5" (lee forense pero no
lanza) sin reestructurar la jerarquía — es solo otro bundle.

---

## Consecuencias

### Positivas

- **Defensa en profundidad**: aunque un workflow n8n sea manipulado, Python
  rechaza acciones no autorizadas. El punto de control es único y testeable.
- **Compliance por diseño**: cada acción destructiva queda ligada a un caso +
  approval + actor + timestamp en audit inmutable.
- **Secretos minimizados**: superficie de exposición de las API keys maestras
  reducida a un solo contenedor.
- **El WCR tracker pierde criticidad**: como n8n ya no decide permisos, el
  riesgo de un cambio no auditado de workflow baja (los workflows operan sobre
  APIs gobernadas). El WCR tracker puede eventualmente retirarse.

### Negativas / costos

- **Latencia extra**: cada acción crítica hace un hop a Python en vez de que
  n8n llame directo. Aceptable — las acciones forenses no son hot-path.
- **Python es punto único de gobernanza**: si el RBAC de Python tiene un bug,
  afecta todo. Mitigación: tests sobre `PermissionChecker` +
  `_enforce_destructive_governance`.
- **Disciplina requerida**: cualquier endpoint nuevo que toque Wazuh/Velo DEBE
  pasar por `PermissionChecker`. Un endpoint olvidado sin gate es una fuga.
  Mitigación: revisión + (futuro) test que verifique que ningún endpoint
  sensible quede sin permiso.

### Brechas de enforcement pendientes (no de arquitectura)

La arquitectura está; falta apretar tuercas (ver
`orchestration-flows.md` §Gobernanza para el detalle):

1. Justificación técnica **obligatoria** en la solicitud de acción destructiva.
2. Nota **bloqueada (no editable)** de auditoría en el caso al autorizar/denegar.
3. **Alerta automática** en el ticket cuando se deniega una acción no autorizada.
4. Definir los **roles L1/L2/Forense** como seed de bundles de capacidades.
5. (Opcional) Token **single-use** (no solo short-lived) para la invocación a
   Velociraptor.

---

## Referencias

- `docs/specs/orchestration-flows.md` — contrato de flujos + §Gobernanza.
- `backend/src/modules/forensic/application/use_cases.py` —
  `_enforce_destructive_governance`.
- `backend/src/modules/n8n_bridge/` — approval flow + callback JWT.
- `backend/src/core/middleware/permission_checker.py` — `PermissionChecker`.
