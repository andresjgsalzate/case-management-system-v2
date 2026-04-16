# Expansión del Sistema de Automatización — Diseño

## Goal

Ampliar el catálogo de disparadores y acciones disponibles en el sistema de automatización para que los usuarios puedan crear reglas más dinámicas, sin cambios de esquema de base de datos.

## Architecture

Se extiende el motor existente en cuatro archivos. No se crean tablas nuevas. Los nuevos triggers se registran en `WATCHED_EVENTS`. Las nuevas acciones se implementan como nuevos `case` branches en `_execute_single_action`. El frontend agrega entradas a los catálogos existentes.

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy async
- **Frontend:** Next.js, React, Tailwind CSS
- **Tabla reutilizada:** `automation_rules`, `cases`, `case_todos`, `case_priorities`

---

## Mapa de archivos

| Archivo | Acción |
|---|---|
| `backend/src/modules/automation/application/handler.py` | Modificar — agregar 6 eventos a `WATCHED_EVENTS` |
| `backend/src/modules/cases/application/use_cases.py` | Modificar — publicar `case.priority_changed` en `update_case` |
| `backend/src/modules/automation/application/use_cases.py` | Modificar — agregar 3 nuevos casos en `_execute_single_action` |
| `frontend/app/(dashboard)/settings/automation/page.tsx` | Modificar — catálogos y params UI |

---

## Componentes

### 1. Nuevos triggers — `handler.py`

Agregar a `WATCHED_EVENTS`:

```python
WATCHED_EVENTS = {
    "case.created",
    "case.status_changed",
    "case.assigned",
    "case.priority_changed",  # ya existía pero el evento no se publicaba — ahora sí
    "sla.breached",
    # nuevos:
    "case.closed",
    "resolution.responded",
    "todo.completed",
    "attachment.uploaded",
    "note.created",
}
```

**Payloads disponibles para condiciones futuras:**

| Evento | Campos en payload |
|---|---|
| `case.closed` | `case_id` |
| `resolution.responded` | `case_id`, `accepted` (bool) |
| `todo.completed` | `case_id`, `todo_id`, `title` |
| `attachment.uploaded` | `case_id`, `attachment_id` |
| `note.created` | `case_id`, `note_id` |

---

### 2. Fix `case.priority_changed` — `cases/application/use_cases.py`

En `update_case`, capturar la prioridad anterior antes del loop de setattr y publicar el evento si cambió:

```python
async def update_case(self, case_id, dto, actor_id, tenant_id):
    case = await self.db.get(CaseModel, case_id)
    ...
    old_priority_id = case.priority_id
    updated_fields = dto.model_dump(exclude_none=True)
    for field, value in updated_fields.items():
        setattr(case, field, value)
    await self.db.commit()
    ...
    # publicar case.updated (ya existe)
    ...
    # nuevo: publicar case.priority_changed si cambió
    if "priority_id" in updated_fields and case.priority_id != old_priority_id:
        await event_bus.publish(BaseEvent(
            event_name="case.priority_changed",
            tenant_id=tenant_id,
            actor_id=actor_id,
            payload={
                "case_id": case_id,
                "from_priority_id": old_priority_id,
                "to_priority_id": case.priority_id,
            },
        ))
```

---

### 3. Nuevas acciones — `automation/application/use_cases.py`

#### `change_status`

Parámetro: `target_status_id` (string UUID).

Lógica: obtiene el caso por `case_id` del contexto, verifica que el estado destino existe, actualiza `status_id` directamente. No valida transiciones permitidas — la automatización puede forzar cualquier estado por diseño. Logea warning si no hay `case_id` en contexto.

```python
case "change_status":
    case_id = context.get("case_id")
    if not case_id:
        logger.warning("change_status: no hay case_id en el contexto")
        return
    target_status_id = action.params.get("target_status_id")
    if not target_status_id:
        logger.warning("change_status: target_status_id no configurado")
        return
    from backend.src.modules.cases.infrastructure.models import CaseModel
    from backend.src.modules.case_statuses.infrastructure.models import CaseStatusModel
    target_status = await self.db.get(CaseStatusModel, target_status_id)
    if not target_status:
        logger.warning("change_status: estado %s no encontrado", target_status_id)
        return
    case = await self.db.get(CaseModel, case_id)
    if not case:
        logger.warning("change_status: caso %s no encontrado", case_id)
        return
    case.status_id = target_status_id
    if target_status.is_final and not case.closed_at:
        from datetime import datetime, timezone
        case.closed_at = datetime.now(timezone.utc)
    logger.info("change_status: caso %s → estado %s", case_id, target_status.name)
```

#### `create_todo`

Parámetros: `title` (texto), `assigned_to_id` (UUID opcional).

Lógica: inserta un `CaseTodoModel` con `case_id` del contexto. `created_by_id` toma el valor de `actor_id` si es un UUID válido, de lo contrario busca el sistema o queda sin asignar (no FK a "system").

```python
case "create_todo":
    case_id = context.get("case_id")
    if not case_id:
        logger.warning("create_todo: no hay case_id en el contexto")
        return
    title = action.params.get("title", "").strip()
    if not title:
        logger.warning("create_todo: título vacío")
        return
    import uuid as _uuid
    from backend.src.modules.todos.infrastructure.models import CaseTodoModel
    # actor_id solo se usa como created_by_id si es UUID válido
    created_by = actor_id if (actor_id and actor_id != "system") else None
    if not created_by:
        logger.warning("create_todo: actor_id '%s' no es válido para FK", actor_id)
        return
    assigned_to = action.params.get("assigned_to_id") or None
    todo = CaseTodoModel(
        id=str(_uuid.uuid4()),
        case_id=case_id,
        created_by_id=created_by,
        assigned_to_id=assigned_to,
        tenant_id=context.get("tenant_id"),
        title=title,
    )
    self.db.add(todo)
    logger.info("create_todo: tarea '%s' creada en caso %s", title, case_id)
```

**Nota:** `create_todo` no funciona con `schedule.daily` (no hay `case_id` en contexto). Funciona con todos los triggers basados en eventos de caso.

#### `escalate_priority`

Sin parámetros.

Lógica: obtiene el caso, consulta todas las prioridades activas del tenant ordenadas por `level` ascendente, encuentra la siguiente con `level > case.priority.level`, y actualiza. Si ya está en el nivel más alto, logea warning y no hace nada.

```python
case "escalate_priority":
    case_id = context.get("case_id")
    if not case_id:
        logger.warning("escalate_priority: no hay case_id en el contexto")
        return
    from backend.src.modules.cases.infrastructure.models import CaseModel
    from backend.src.modules.case_priorities.infrastructure.models import CasePriorityModel
    from sqlalchemy import asc
    case = await self.db.get(CaseModel, case_id)
    if not case or not case.priority_id:
        logger.warning("escalate_priority: caso %s no encontrado o sin prioridad", case_id)
        return
    current_priority = await self.db.get(CasePriorityModel, case.priority_id)
    if not current_priority:
        return
    result = await self.db.execute(
        select(CasePriorityModel).where(
            CasePriorityModel.is_active.is_(True),
            CasePriorityModel.level > current_priority.level,
            CasePriorityModel.tenant_id == case.tenant_id,
        ).order_by(asc(CasePriorityModel.level)).limit(1)
    )
    next_priority = result.scalar_one_or_none()
    if not next_priority:
        logger.info("escalate_priority: caso %s ya tiene la prioridad más alta", case_id)
        return
    case.priority_id = next_priority.id
    logger.info(
        "escalate_priority: caso %s escalado de nivel %d → %d",
        case_id, current_priority.level, next_priority.level,
    )
```

---

### 4. Frontend — `settings/automation/page.tsx`

#### `EVENT_LABELS` — agregar 5 entradas (6to ya existe):

```typescript
"case.closed":           "Caso cerrado",
"resolution.responded":  "Solicitante respondió",
"todo.completed":        "Tarea completada",
"attachment.uploaded":   "Archivo adjunto",
"note.created":          "Nota agregada",
```

`"case.priority_changed"` ya existe en `EVENT_LABELS`.

#### `ACTION_TYPES` — agregar 3 entradas:

```typescript
change_status:     "Cambiar estado",
create_todo:       "Crear tarea",
escalate_priority: "Escalar prioridad",
```

#### `ActionRow` — 3 bloques de params:

**`change_status`:**
```tsx
{action.action_type === "change_status" && (
  <div className="pl-1">
    <label className="text-xs text-muted-foreground">Estado destino</label>
    <select
      className="mt-1 w-full px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
      value={action.params.target_status_id ?? ""}
      onChange={(e) => setParam("target_status_id", e.target.value)}
    >
      <option value="">— seleccionar estado —</option>
      {statuses.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
    </select>
  </div>
)}
```

**`create_todo`:**
```tsx
{action.action_type === "create_todo" && (
  <div className="flex flex-col gap-2 pl-1">
    <div>
      <label className="text-xs text-muted-foreground">Título de la tarea</label>
      <input
        className="mt-1 w-full px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
        placeholder="Ej: Verificar documentación"
        value={action.params.title ?? ""}
        onChange={(e) => setParam("title", e.target.value)}
      />
    </div>
    <div>
      <label className="text-xs text-muted-foreground">Asignar a (opcional)</label>
      <select
        className="mt-1 w-full px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
        value={action.params.assigned_to_id ?? ""}
        onChange={(e) => setParam("assigned_to_id", e.target.value)}
      >
        <option value="">— sin asignar —</option>
        {users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
      </select>
    </div>
  </div>
)}
```

**`escalate_priority`:**
```tsx
{action.action_type === "escalate_priority" && (
  <p className="pl-1 text-xs text-muted-foreground">
    Sube la prioridad del caso un nivel. Si ya está en el nivel más alto, no hace nada.
  </p>
)}
```

#### Inicialización de defaults en `onChange` del selector de acción:

```typescript
const defaultParams: Record<string, string> =
  type === "archive_closed_cases" ? { days_after_close: "30" }
  : type === "create_todo"        ? { title: "" }
  : {};
```

---

## Data flow

```
Usuario configura regla
  trigger_event: "sla.breached"
  actions: [{ action_type: "escalate_priority" }, { action_type: "send_notification", ... }]
        ↓
SLA job publica sla.breached
        ↓
AutomationHandler.handle() — evento en WATCHED_EVENTS → evaluate_and_execute()
        ↓
_execute_single_action("escalate_priority") → busca nivel siguiente → actualiza priority_id
_execute_single_action("send_notification") → publica notification.create
```

---

## Consideraciones

- **`create_todo` con `schedule.daily`:** No tiene `case_id` en contexto → la acción logea warning y retorna. Es responsabilidad del usuario no combinar este trigger con `create_todo`.
- **`change_status` circular:** Si `case.closed` dispara `change_status → cerrado`, el caso ya estará cerrado y simplemente se re-asignará el mismo estado. No es un bug pero no tiene efecto útil.
- **Sin migración de BD:** Todas las tablas usadas (`cases`, `case_todos`, `case_priorities`, `case_statuses`) ya existen.
- **Idempotencia de `escalate_priority`:** Si el nivel más alto ya está asignado, no hace nada — seguro para re-ejecuciones.
