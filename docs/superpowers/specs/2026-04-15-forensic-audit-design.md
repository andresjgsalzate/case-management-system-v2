# Auditoría Forense — Diseño de Mejoras

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevar el sistema de auditoría existente a nivel forense: captura completa del estado anterior en UPDATEs, correlación de cambios por request HTTP, contexto de operación (user agent, ruta), e inmutabilidad garantizada a nivel de base de datos.

**Architecture:** Se extiende el middleware SQLAlchemy existente con nuevas columnas en `audit_logs`, un middleware HTTP Starlette que inyecta contexto de request, y dos nuevos endpoints para consultas forenses. El frontend añade línea de tiempo por entidad y panel de operación correlacionada.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL (trigger PL/pgSQL), Alembic, React/Next.js, TanStack Query

---

## Escenarios cubiertos

1. **Investigación de incidentes** — dado un entity_type + entity_id, reconstruir el estado completo del registro desde su creación hasta hoy.
2. **Rendición de cuentas** — cada registro de auditoría incluye actor resuelto, navegador, ruta HTTP y timestamp exacto.
3. **Inmutabilidad** — trigger PostgreSQL impide UPDATE o DELETE sobre `audit_logs`; ni el superusuario de la app puede alterar registros.

---

## Sección 1: Modelo de datos

### Nuevas columnas en `audit_logs`

| Columna | Tipo SQLAlchemy | Nullable | Índice | Descripción |
|---|---|---|---|---|
| `correlation_id` | `String(36)` | Sí | Sí | UUID generado una vez por request HTTP. Todos los `AuditLogModel` creados en esa transacción comparten el mismo valor. |
| `before_snapshot` | `JSON` | Sí | No | Solo para UPDATE: estado completo del registro *antes* de la modificación. Permite reconstrucción de estado en cualquier punto del tiempo. |
| `user_agent` | `String(500)` | Sí | No | Valor del header `User-Agent` de la solicitud HTTP, truncado a 500 caracteres. |
| `request_path` | `String(200)` | Sí | No | Método + ruta HTTP de la operación, ej: `PATCH /api/v1/cases/abc123`. |

### Migración Alembic

La migración añade las columnas y crea el trigger de inmutabilidad:

```sql
-- Trigger de inmutabilidad
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs records are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_logs_immutable
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
```

El `down` de la migración elimina el trigger y las columnas.

---

## Sección 2: Middleware de captura (`middleware.py`)

### ContextVars extendidos

Se añaden tres ContextVars junto al existente `_current_actor`:

```python
_current_correlation: ContextVar[str | None]  # UUID del request
_current_user_agent:  ContextVar[str | None]  # User-Agent header
_current_request_path:ContextVar[str | None]  # "METHOD /path"
```

### Función `set_audit_context`

Reemplaza `set_current_actor` como punto de entrada principal. `set_current_actor` queda como alias de compatibilidad que solo actualiza `_current_actor`.

```python
def set_audit_context(
    actor_id: str | None,
    correlation_id: str | None,
    user_agent: str | None = None,
    request_path: str | None = None,
) -> None
```

### Nueva función `_get_before_snapshot`

Para eventos UPDATE, reconstruye el estado completo *anterior* usando `attr.history` en `before_flush`. Para campos modificados usa `hist.deleted[0]`; para campos sin cambios usa el valor actual.

```python
def _get_before_snapshot(instance) -> dict:
    # Para cada attr:
    #   si hist.has_changes(): value = hist.deleted[0] if hist.deleted else None
    #   si no: value = getattr(instance, attr.key)
    # Serializar igual que _get_snapshot (datetime.isoformat, uuid.str, etc.)
```

### Listener `before_flush` actualizado

Todos los `AuditLogModel` que se crean reciben los cuatro campos nuevos:
- `correlation_id = _current_correlation.get()`
- `before_snapshot = _get_before_snapshot(instance)` (solo UPDATE, None para INSERT/DELETE)
- `user_agent = _current_user_agent.get()`
- `request_path = _current_request_path.get()`

---

## Sección 3: Middleware HTTP de FastAPI (`audit_context.py`)

Archivo nuevo: `backend/src/core/middleware/audit_context.py`

```python
class AuditContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        correlation_id = str(uuid.uuid4())
        set_audit_context(
            actor_id=None,   # el dependency CurrentUser lo sobreescribe después
            correlation_id=correlation_id,
            user_agent=request.headers.get("user-agent", "")[:500],
            request_path=f"{request.method} {request.url.path}"[:200],
        )
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response
```

Se registra en `main.py` con `app.add_middleware(AuditContextMiddleware)`.

El dependency `CurrentUser` existente sigue llamando `set_current_actor(user_id)` — ahora solo actualiza el ContextVar del actor sin pisar el `correlation_id` ya fijado por el middleware.

**Invariante:** cada request HTTP tiene exactamente un `correlation_id`. El header `X-Correlation-Id` en la respuesta permite correlacionar errores del frontend con cambios en BD.

---

## Sección 4: Endpoints nuevos

### `GET /api/v1/audit/timeline/{entity_type}/{entity_id}`

Devuelve todos los eventos de una entidad en orden **cronológico ASC** (del más antiguo al más reciente). Incluye `before_snapshot`, `changes`, `correlation_id`, `actor_name`, `request_path`, `user_agent`. Permite reconstruir el estado completo del registro desde su creación.

Requiere permiso `audit.read`.

### `GET /api/v1/audit/operation/{correlation_id}`

Devuelve todos los logs que comparten ese `correlation_id`, en orden cronológico. Permite responder: *"en el mismo request que se cerró este caso, ¿qué otros registros se modificaron?"*

Requiere permiso `audit.read`.

Ambos endpoints reutilizan el serializer `_serialize` existente, extendido con los cuatro campos nuevos.

---

## Sección 5: Frontend

### Tipo `AuditLog` (types.ts)

```typescript
export interface AuditLog {
  // campos existentes...
  correlation_id?: string | null;
  before_snapshot?: Record<string, unknown> | null;
  user_agent?: string | null;
  request_path?: string | null;
}
```

### A) Botón "Ver línea de tiempo" en la tabla

Cada fila de la tabla de auditoría tiene un segundo icono (además del chevron) que abre un drawer/modal de línea de tiempo. Llama a `GET /audit/timeline/{entity_type}/{entity_id}` y muestra todos los eventos del registro en orden cronológico con sus badges de acción y fechas.

### B) Panel "Operación completa" en el modal de detalle

Cuando un log tiene `correlation_id`, aparece una sección colapsada al final del modal:

```
Operación completa  [X eventos en este request]
  · PATCH /api/v1/cases/abc — hace 2 días
    Casos › REQ-042 — Título del caso        [Edición]
    Usuarios › Juan Pérez (juan@example.com) [Edición]
```

Llama a `GET /audit/operation/{correlation_id}`. Excluye el log actual de la lista para evitar duplicado.

### C) "Estado anterior completo" en el modal de detalle

Para eventos UPDATE que tengan `before_snapshot`, aparece un acordeón colapsado **encima** de la tabla de campos modificados con el label "Estado antes del cambio". Muestra todos los campos del `before_snapshot` en una tabla de dos columnas (Campo / Valor), usando `FIELD_LABELS` para los nombres y sin mostrar `id`, `tenant_id`, `usage_count`.

---

## Límites del diseño

- Los registros anteriores a esta migración no tendrán `correlation_id`, `before_snapshot`, `user_agent` ni `request_path` — esos campos quedan `null`.
- El trigger de inmutabilidad se aplica a partir de la migración. Los registros existentes no están protegidos retroactivamente (están en BD, no han sido alterados, pero el trigger no aplica a ellos de forma diferente — los protege a partir de ahora).
- No se incluye exportación CSV/PDF en este alcance.
- No se incluyen alertas ni reglas de detección de anomalías en este alcance.
