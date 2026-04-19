# Helpdesk Permissions & Levels — Design Spec

**Fecha:** 2026-04-18
**Autor:** andresjgsalzate + Claude
**Estado:** Propuesta — pendiente de revisión

---

## 1. Contexto y problema

El sistema actual tiene RBAC con scopes `{own, team, all}` pero la UI de administración de roles guarda **siempre** `scope: "all"` (`frontend/app/(dashboard)/settings/roles/page.tsx:170`), lo cual rompe el contrato del backend. Además, el frontend de casos (`frontend/app/(dashboard)/cases/[id]/page.tsx:113-114`) usa un guardia binario:

```ts
const caseAssignedToOther = !!c.assigned_to && c.assigned_to !== currentUserId;
const canTakeActions = canAssignAny || !caseAssignedToOther;
```

El síntoma reportado: *"a pesar de que el rol tiene todos los permisos no puede realizar acciones sobre el caso como clasificar, asignar, cambiar estados"*. La causa: un resolutor con `cases:update:team` no puede tocar un caso que alguien más del equipo tiene asignado, aunque legítimamente debería.

Además, el modelo actual no soporta el flujo estándar de helpdesk:
- Reporters (solo sus casos, acciones limitadas).
- Resolvers en niveles N1/N2 con escalamiento/de-escalamiento.
- Búsqueda transversal por número de caso.
- Colaboración multi-actor en un caso sin romper la responsabilidad de quien lo tiene asignado.

Este spec define el rediseño completo para soportar ese modelo.

---

## 2. Decisiones de diseño (locked in)

1. **Team multi-nivel.** Un team puede contener miembros con `level` distinto. El team no tiene level propio — hereda de sus miembros.
2. **Modelo híbrido de colaboración.** Cualquier resolutor con acceso al caso (por asignación, equipo o búsqueda por número) puede agregar notas, adjuntos y chat; pero **transiciones de estado, reasignación y escalamiento** quedan restringidas al asignado actual o a quien tenga scope suficiente.
3. **`level` como INT en `roles`.** Campo entero ≥0, default 1. `level=0` reservado para roles no-resolutores (reporter, admin puro). `level≥1` son tiers de resolución. Sin enum ni tabla separada — se admiten N1, N2, N3… según necesidad futura.
4. **`current_level` como INT en `cases`.** Default 1. La auto-asignación a un resolutor N2 **no cambia** `current_level` (variante B1 de la conversación); solo una acción explícita de transfer modifica el nivel.
5. **Acción única `transfer`.** La UI presenta siempre un solo flujo ("Transferir caso" → elegir team + persona + motivo). El backend clasifica el movimiento en *escalate* / *reassign* / *de-escalate* comparando `role.level` origen vs. destino.
6. **Búsqueda por número = lectura + colaboración.** Encontrar un caso por `case_number` desbloquea leer, comentar, adjuntar y chatear, pero **no** transicionar estados ni reasignar.
7. **Listado híbrido A+C.** La vista principal muestra *mi cola por nivel* (estricto: casos donde `current_level == role.level` y team del usuario); una pestaña secundaria *Equipo* muestra todos los casos del team sin importar nivel.

---

## 3. Modelo de datos

### 3.1 Cambios en `roles`

```sql
ALTER TABLE roles ADD COLUMN level INTEGER NOT NULL DEFAULT 1;
ALTER TABLE roles ADD CONSTRAINT roles_level_non_negative CHECK (level >= 0);
CREATE INDEX idx_roles_level ON roles(level);
```

Semántica: `level = 0` reservado para roles no-resolutores (reporter, admin puro). `level >= 1` son tiers de resolución. Se almacena como INT, no enum, para permitir añadir N3/N4 sin migración.

### 3.2 Cambios en `cases`

```sql
ALTER TABLE cases ADD COLUMN current_level INTEGER NOT NULL DEFAULT 1;
ALTER TABLE cases ADD CONSTRAINT cases_current_level_positive CHECK (current_level >= 1);
CREATE INDEX idx_cases_current_level ON cases(current_level);
```

Semántica: representa el nivel *actualmente responsable* del caso. Solo un `transfer` explícito lo modifica.

### 3.3 Nueva tabla `case_transfers`

```sql
CREATE TABLE case_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    from_user_id UUID NULL REFERENCES users(id),
    from_level INTEGER NOT NULL,
    to_user_id UUID NOT NULL REFERENCES users(id),
    to_team_id UUID NOT NULL REFERENCES teams(id),
    to_level INTEGER NOT NULL,
    transfer_type VARCHAR(16) NOT NULL,  -- 'escalate' | 'reassign' | 'de-escalate'
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT transfers_type_valid CHECK (transfer_type IN ('escalate','reassign','de-escalate')),
    CONSTRAINT transfers_reason_nonempty CHECK (length(trim(reason)) > 0)
);
CREATE INDEX idx_case_transfers_case_id ON case_transfers(case_id, created_at DESC);
```

El `transfer_type` lo calcula el backend — la UI nunca lo pide. Se retiene para auditoría y reporting.

### 3.4 Permission scopes vigentes

Se conserva `scope ∈ {own, team, all}` como hoy. Se añade matiz: `team` ahora significa *todos los miembros del team sin importar level*. Es responsabilidad del listado filtrar por level cuando corresponda (ver §5).

---

## 4. Modelo de permisos y reglas de decisión

### 4.1 Función central `check_case_action`

Un único helper resuelve TODOS los gates de caso. Firma propuesta (Python):

```python
def check_case_action(
    user: CurrentUser,
    case: Case,
    action: Literal["read", "update", "transition", "transfer", "comment", "attach"],
    user_role_level: int,
) -> bool:
    ...
```

**Tabla de decisión:**

| Acción       | Reporter (level=0)              | Resolver con scope `own`     | Resolver con scope `team`                 | Resolver con scope `all` |
|--------------|---------------------------------|------------------------------|-------------------------------------------|--------------------------|
| `read`       | Solo si `created_by == user.id` | Asignado, creador, o transfer origen | Miembro mismo team que asignado           | Siempre                  |
| `comment`    | `read` + caso no cerrado        | `read`                       | `read`                                    | `read`                   |
| `attach`     | `read` + caso no cerrado        | `read`                       | `read`                                    | `read`                   |
| `update`     | Solo creador, campos limitados  | Solo si `assigned_to == user.id` | Miembro mismo team (aunque no sea asignado) | Siempre                  |
| `transition` | No                              | Solo si `assigned_to == user.id` | Solo si `assigned_to == user.id` O `user_role_level > case.current_level` | Siempre |
| `transfer`   | No                              | Solo si `assigned_to == user.id` | Asignado o level >= `current_level`       | Siempre                  |

**Regla clave:** `update` sobre un caso con otro asignado está permitido a compañeros de team con `scope=team` (resuelve el bug reportado). Pero `transition` sigue siendo más estricta para preservar la responsabilidad.

**"Búsqueda por número" ≡ lectura:** Si el usuario consulta `GET /cases/{number}` y no pasa los filtros de listado, igual obtiene el caso si el backend determina que `read` es True. Comentar/adjuntar automáticamente quedan habilitados por la tabla. Transicionar y transfer no.

### 4.2 Middleware y scope

- `/auth/me` ya devuelve `permissions: [{module, action, scope}]`. Se mantiene.
- Se añade al payload: `role_level: int` (top-level, no dentro del array de permisos).
- `CurrentUser` dataclass (`backend/src/core/middleware/permission_checker.py`) gana el campo `role_level: int`.
- Los endpoints REST dejan de hacer chequeos ad-hoc y pasan todos por `check_case_action`.

### 4.3 UI de administración de roles

Reemplazar el checkbox binario por un **selector de 4 estados**: `None | own | team | all`. El bug hardcoded (`perms.push({ module, action, scope: "all" })`) desaparece.

Adicionalmente, añadir un campo `level` (input numérico 0..N) en el formulario de rol, al lado de `name` y `description`. Tooltip: *"Nivel de escalamiento (0 = no resolutor, 1 = primer nivel, 2 = segundo nivel…)"*.

---

## 5. Flujos end-to-end

### 5.1 Flujo "crear caso como reporter"

1. Reporter crea caso → `current_level = 1`, `assigned_to = NULL`.
2. Auto-routing actual (fuera de scope de este spec) lo asigna al N1 menos cargado — **sin cambiar `current_level`**.
3. Reporter ve en su listado *mis casos*. Ve notas, chat y actividad. Puede cerrar *solo si* tiene `cases:update:own` y el status destino es cierre por reporter (fuera de scope; asumimos que existe).

### 5.2 Flujo "resolutor N1 toma acción"

1. N1 logueado → listado muestra tab *Mi cola* (`current_level=1` AND team del usuario AND `assigned_to=user` OR unassigned) + tab *Equipo*.
2. N1 clickea caso → puede cambiar status, comentar, clasificar. La lógica `canTakeActions` desaparece; todos los botones se condicionan por `check_case_action` + permissions del user.
3. N1 decide escalar → presiona *Transferir*. Modal pide: team destino, usuario destino (autocomplete filtrado por team), motivo.
4. N1 elige un N2 → backend valida que el N1 es el asignado (o tiene `transfer:all`), calcula `transfer_type="escalate"` (porque `user_role_level < target_role.level`), actualiza `case.current_level = 2`, `case.assigned_to = target`, crea registro en `case_transfers`.

### 5.3 Flujo "N2 de-escala al N1 original"

1. N2 abre caso, ve historial de transfers en el drawer lateral.
2. Presiona *Transferir*, elige al N1 original, motivo.
3. Backend clasifica como `de-escalate`, actualiza `current_level = 1`, `assigned_to`, registra.
4. N1 recibe notificación (reutiliza el sistema existente `case_assigned`).

### 5.4 Flujo "buscar caso por número y colaborar"

1. N2 recibe consulta externa sobre caso `CASE-1234` que no le pertenece.
2. Busca en top-bar → ingresa número → frontend hace `GET /cases/by-number/{number}`.
3. Backend: `check_case_action(user, case, "read", user_level)` → True si tiene `cases:read:all` o `cases:read:team` y es mismo team; False si `scope=own`. **Búsqueda por número requiere al menos `scope=team` o explícitamente `cases:read:all`.**
4. Si tiene acceso, abre detalle completo. UI oculta botones de `transition`/`transfer` si `check_case_action` dice no. Comentar/adjuntar/chat permitido.

### 5.5 Flujo "reasignación entre pares del mismo nivel"

N1 está OOO, otro N1 del team toma su caso:

1. Cualquier N1 del team con `cases:transfer:team` presiona *Transferir* en un caso del compañero.
2. Elige otro N1 del team, motivo.
3. Backend calcula `transfer_type="reassign"` (mismo nivel), no toca `current_level`, actualiza `assigned_to`.

---

## 6. Tests, migración, riesgos

### 6.1 Migración (Alembic, un solo step)

```python
def upgrade() -> None:
    op.add_column("roles", sa.Column("level", sa.Integer(), nullable=False, server_default="1"))
    op.create_check_constraint("roles_level_non_negative", "roles", "level >= 0")
    op.create_index("idx_roles_level", "roles", ["level"])

    op.add_column("cases", sa.Column("current_level", sa.Integer(), nullable=False, server_default="1"))
    op.create_check_constraint("cases_current_level_positive", "cases", "current_level >= 1")
    op.create_index("idx_cases_current_level", "cases", ["current_level"])

    op.create_table(
        "case_transfers",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_user_id", UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("from_level", sa.Integer(), nullable=False),
        sa.Column("to_user_id", UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("to_team_id", UUID(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("to_level", sa.Integer(), nullable=False),
        sa.Column("transfer_type", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("transfer_type IN ('escalate','reassign','de-escalate')", name="transfers_type_valid"),
        sa.CheckConstraint("length(trim(reason)) > 0", name="transfers_reason_nonempty"),
    )
    op.create_index("idx_case_transfers_case_id", "case_transfers", ["case_id", "created_at"])
```

**Backfill:** roles existentes quedan con `level=1` — correcto para roles resolutores. El admin debe ajustar manualmente el rol *reporter* a `level=0` tras la migración (nota para release notes).

### 6.2 Tests críticos

**Unit tests sobre `check_case_action`** (archivo nuevo `backend/tests/core/test_case_permissions.py`): toda la matriz §4.1 debe cubrirse — mínimo 24 casos (6 acciones × 4 perfiles), más edge cases:
- Reporter intentando transicionar → False.
- Resolver `scope=team` modificando caso de compañero → True para `update`, False para `transition`.
- `scope=all` siempre True salvo reglas inmutables (ej. caso archivado).
- `transfer` con `from_level < to_level` clasifica `escalate`; `==` → `reassign`; `>` → `de-escalate`.

**Integración:**
- Endpoint `POST /cases/{id}/transfer` crea `case_transfers` + actualiza `assigned_to` + `current_level`.
- `GET /cases` filtrado por *mi cola* devuelve solo casos con `current_level == user.role_level` AND team del usuario.
- UI `settings/roles/page.tsx` guarda y recupera `scope` correctamente para los 3 valores.

### 6.3 Fuera de scope (explícito, NO hacer)

- Auto-routing mejorado (selección inteligente del N1 menos cargado): el routing actual se respeta tal cual.
- SLA por nivel (ej. "N1 tiene 4h, N2 tiene 24h"): el SLA actual es global.
- Concepto de *supervisor* o líder de team: no existe, cualquiera del team con permisos puede transferir.
- Vistas de cola agregadas tipo "todas las colas del tenant": solo el admin con `scope=all` verá todo.
- Reglas de horario / guardia: fuera de scope.

### 6.4 Riesgos

| Riesgo                                                                                         | Mitigación                                                                                        |
|------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| El selector 4-estados en admin de roles se rompe con data legacy (todo guardado como `all`)    | Migración lee valores existentes y los mantiene. Admin debe revisar roles tras deploy.           |
| `check_case_action` es nuevo y central — un bug afecta TODO                                    | Cobertura ≥95% en el archivo. Smoke test E2E antes de merge: reporter, N1, N2, admin.            |
| Reporters ven botones que no pueden usar (mala UX)                                             | Frontend también consulta permissions. La UI oculta; el backend es la fuente de verdad.          |
| Casos archivados siguen siendo transferibles por error                                         | `check_case_action` valida `case.is_archived` antes de cualquier acción escribible.              |
| Equipos muy grandes → listado *Equipo* lento                                                   | Paginación existente ya cubre. Index en `current_level` acelera *Mi cola*.                       |

---

## 7. Plan de implementación sugerido (alto nivel)

Este spec alimenta un plan TDD detallado en la fase siguiente. Esquema tentativo:

1. Migración + modelos SQLAlchemy (roles.level, cases.current_level, case_transfers).
2. `check_case_action` + tests unitarios completos.
3. Refactor endpoints `/cases/**` para usar el helper.
4. Endpoint `POST /cases/{id}/transfer`.
5. Exponer `role_level` en `/auth/me` y `CurrentUser`.
6. UI admin roles: selector 4 estados + input level.
7. Frontend `useHasPermission` → recibe caso opcional, calcula con lógica equivalente.
8. Componente `TransferCaseModal` (team + usuario + motivo).
9. Reemplazar `canTakeActions` binario en `cases/[id]/page.tsx` por llamadas granulares al helper.
10. Listado *Mi cola* vs. *Equipo* en `cases/page.tsx`.
11. E2E smoke test del flujo completo reporter→N1→N2→N1.

---

## 8. Glosario

- **Level / Nivel:** entero ≥0 en el rol. 0 = no resolutor, 1+ = tiers de escalamiento.
- **Current level:** nivel actualmente responsable de un caso (≥1).
- **Escalate:** transfer con `to_level > from_level`.
- **Reassign:** transfer con `to_level == from_level`.
- **De-escalate:** transfer con `to_level < from_level`.
- **Scope:** alcance de un permiso. `own` = solo los propios, `team` = mismo team sin importar level, `all` = global.
