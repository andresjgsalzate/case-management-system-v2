# Triage SOC — especificación

Documento de especificación del módulo de **Triage SOC** que se integrará
al detalle del caso bajo la pestaña Seguridad. Captura el comportamiento
esperado para Fase 2 (backend + modelo de datos) y Fase 3 (UI).

> **Estado actual** (Fase 1 ya implementada):
> El tab "Seguridad" se muestra solo cuando el caso tiene una taxonomía
> asignada (`case.taxonomy_id IS NOT NULL`). El resto de lo descrito en
> este documento todavía no está implementado.

---

## 1. Objetivo

Reemplazar la práctica actual de "triage como texto libre en notas + adjuntos
sueltos + generación tardía del Alert Report" por un **formulario estructurado**
ejecutado durante la atención del caso, que:

1. Auto-rellena campos derivables del caso, taxonomía, usuario, tenant.
2. Pide al analista solo los datos genuinamente nuevos (severidad, impacto,
   herramienta origen, narrativa).
3. **Recalcula la prioridad del caso** usando una matriz parametrizable.
4. Sirve como **fuente única** para los bloques del Alert Report.

---

## 2. Campos del triage

### 2.1 Auto-derivados (calculados, no editables salvo override)

| Campo | Fuente |
|---|---|
| **Título del evento** | `case.title` (default, modificable solo en triage) |
| **Cliente** | `tenants.name` resuelto de `case.tenant_id` |
| **Fecha caso / Hora caso / Ofensa No.** | `case.created_at`, `case.case_number` |
| **Notificado por / Cargo / Contacto** | usuario `case.created_by` (full_name, role, email) |
| **Clasificación Incidente** | Taxonomía **padre** del caso |
| **Sub-clasificación** | Taxonomía **hijo** seleccionada por el analista (lista filtrada por padre) |
| **Impacto potencial** | Lookup en sub-clasificación según contexto:<br>• si `Contexto Origen = Origen Interno` → `taxonomy.internal_impact_context`<br>• si `Contexto Origen = Origen Externo` → `taxonomy.external_impact_context` |
| **NIVEL CRITICIDAD / PRIORIDAD** | Calculado vía matriz §3 |

### 2.2 Listas fijas (Literal en backend, dropdown en frontend)

| Campo | Valores |
|---|---|
| **Severidad de la alerta** | `Crítico`, `Alto`, `Medio`, `Bajo`, `Falso Positivo` |
| **Contexto Origen alerta — tipo** | `Origen Interno`, `Origen Externo` |
| **Criticidad de activo** | `Crítico`, `Alto`, `Medio`, `Bajo` |

> **Nota**: `Falso Positivo` aparece en la lista de **Severidad** **y** también es una clasificación
> de **Taxonomía** válida (root: `Falso Positivo` con sub `Falso Positivo`,
> impactos internos/externos = `Falso Positivo`). Cuando el analista determina
> que el evento no representa riesgo, marca la severidad como FP **y** opcionalmente
> reclasifica la taxonomía a FP. Ver xlsx `Taxonomía v9!R7`.

### 2.2.b Correlación TLP ↔ Criticidad ↔ Valoración

El xlsx `Priorización!R24-R28` define un aliasing entre el TLP de la taxonomía
y la Criticidad de activo, mapeados al mismo valor numérico de la matriz:

| TLP (de la taxonomía) | Criticidad | Valoración |
|---|---|---|
| `TLP:RED` | `Crítico` | **5** |
| `TLP:AMBER` | `Alto` | **4** |
| `TLP:GREEN` | `Medio` | **3** |
| `TLP:CLEAR` (white) | `Bajo` | **2** |

**Implicación de diseño**: la Criticidad de activo puede inicializarse al TLP
de la taxonomía seleccionada (auto-fill) y el analista puede overridear si la
realidad del activo difiere. El cálculo de la matriz usa la **valoración
numérica final** independiente de si vino del TLP o del override manual.

### 2.3 Listas parametrizables (tablas catálogo editables desde `/settings`)

| Tabla nueva | Propósito | Valores literales del xlsx |
|---|---|---|
| `triage_tool_types` | Tipo de herramienta origen del evento (xlsx `Herramientas!R9-R23`) | FW Externo, FW Interno, AD-Controller, EDR, Server, WAF, Base de datos, Equipos Red, Linux, Office365, ZTNA, AntiSPAM, Backup, Equipos de computo, **NGFWG** |
| `triage_tool_actions` | "Acción aplicada" sobre la herramienta (xlsx `Triage!R17 col C`) | `Monitoreo`, `Bloqueo` (extensible) |
| `triage_sla_policies` | SLA por nivel de prioridad calculada | Crítico → 20 min, Alto → 40 min, Medio → 120 min, Bajo → 12 h, Falso Positivo → N/A |

Todas con CRUD admin en `/settings/triage-catalogs` (o equivalente).

> **Nota nomenclatura**: el xlsx llama al modo de la herramienta **"Acción
> aplicada"** (no "Modo herramienta"). El campo backend se llama
> `triage_tool_actions` para mantener consistencia con la palabra del cliente.

> **Nota typo**: el xlsx tiene `NGFWG` en el último item (probable typo de
> NGFW + G). Importar literal para no perder fidelidad con el documento
> operacional del cliente; renombrar si confirma que es typo.

### 2.4 Campos libres

| Campo | Tipo | Notas |
|---|---|---|
| **Contexto Origen alerta — detalle** | string | IP / Red / Correo / etc. |
| **Activo relacionado** | string | IP / Red / Nombre del activo objetivo |
| **Duración de la alerta** | string (formato `hh:mm`) o `interval` | Tiempo desde detección hasta cierre |
| **Repeticiones de la alerta** | int | Cuántas veces se observó la misma alerta |
| **Análisis** (narrativa) | text | Describir hechos: qué, cómo, cuándo, hipótesis, impacto potencial |
| **Comportamiento de la alerta** | text | Relación con otras alertas/eventos previos |
| **Recomendaciones** | text | Pasos sugeridos para atender la alerta |
| **Evidencia (imagen)** | FK a `case_attachments` | Screenshot de la alerta original |
| **Comportamiento (imagen)** | FK a `case_attachments` | Screenshot/diagrama de la relación con otras alertas |

---

## 3. Matriz de cálculo de prioridad (parametrizable)

### 3.1 Fórmula

```
score = (severidad_alerta_calif × 0.50)
      + (impacto_potencial_calif × 0.30)
      + (criticidad_activo_calif × 0.20)
```

### 3.2 Calificación numérica de cada nivel

| Nivel | Calificación |
|---|---|
| Crítico | 5 |
| Alto | 4 |
| Medio | 3 |
| Bajo | 2 |
| Falso Positivo | 0 |

> El xlsx `Priorización!R25-R28` solo enumera 4 niveles (Crítico, Alto, Medio,
> Bajo). `Falso Positivo` no está en la tabla numérica del xlsx pero aparece
> en el mapping de SLA (R22: "Falso Positivo → N/A"). El comportamiento
> esperado: si la severidad es FP, **se omite el cálculo de matriz** y la
> prioridad resultante es directamente "Falso Positivo" con SLA N/A. No se
> multiplica por pesos. Tratar como caso especial en el use case.
>
> "Informativo" NO está en el xlsx — removido de esta versión del spec.
> Si surge la necesidad, agregarlo después.

(Esto debería vivir en `prioritization_scales` ya existente — reutilizar
schema, no crear tabla nueva.)

### 3.3 Mapping score → nivel de prioridad final

| Score | Prioridad |
|---|---|
| 4.5 – 5.0 | Crítico |
| 3.5 – 4.4 | Alto |
| 2.5 – 3.4 | Medio |
| 1.0 – 2.4 | Bajo |
| 0 (cualquier input = Falso Positivo) | Falso Positivo |

(Tabla `prioritization_thresholds` ya existe — reutilizar.)

### 3.4 SLA derivado de la prioridad calculada

| Prioridad | Tiempo notificación |
|---|---|
| Crítico | 20 minutos |
| Alto | 40 minutos |
| Medio | 120 minutos |
| Bajo | 12 horas |
| Falso Positivo | N/A |

Estos valores viven en `triage_sla_policies` (parametrizable). Al guardar
el triage, el sistema actualiza `case.due_date` (o equivalente) usando
`triage_created_at + sla_minutes`.

---

## 4. Modelo de datos propuesto

### 4.1 Tabla `case_triages`

Una entrada por revisión de triage. Versionado simple: cada save crea una
nueva row; el "actual" es la más reciente por `case_id`.

```sql
CREATE TABLE case_triages (
  id                          VARCHAR(36) PRIMARY KEY,
  case_id                     VARCHAR(36) NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  version                     INTEGER NOT NULL DEFAULT 1,
  triaged_by_user_id          VARCHAR(36) NOT NULL REFERENCES users(id),
  triaged_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Snapshot del caso al momento del triage (evita drift si el caso cambia)
  case_title_snapshot         VARCHAR(500) NOT NULL,
  case_tenant_name_snapshot   VARCHAR(200),

  -- Clasificación (FK a sub-clasificación; el padre se infiere)
  sub_taxonomy_id             VARCHAR(36) NOT NULL REFERENCES security_taxonomies(id),

  -- Listas fijas (Literal enforced en Pydantic)
  alert_severity              VARCHAR(20) NOT NULL,   -- critico|alto|medio|bajo|falso_positivo
  context_origin_type         VARCHAR(20) NOT NULL,   -- origen_interno|origen_externo
  asset_criticality           VARCHAR(20) NOT NULL,   -- critico|alto|medio|bajo

  -- Listas parametrizables (FK a tablas catálogo)
  tool_type_id                VARCHAR(36) REFERENCES triage_tool_types(id),
  tool_action_id              VARCHAR(36) REFERENCES triage_tool_actions(id),

  -- Campos libres
  context_origin_detail       VARCHAR(500),           -- IP/Red/Correo
  related_asset               VARCHAR(500),           -- IP/Red/Activo
  alert_duration_seconds      INTEGER,
  alert_repetitions           INTEGER DEFAULT 1,

  -- Narrativos
  analysis_narrative          TEXT,
  behavior_narrative          TEXT,
  recommendations             TEXT,

  -- Adjuntos semánticos
  evidence_attachment_id      VARCHAR(36) REFERENCES case_attachments(id),
  behavior_attachment_id      VARCHAR(36) REFERENCES case_attachments(id),

  -- Resultado del cálculo (denormalizado para reportería rápida)
  calculated_priority_id      VARCHAR(36) REFERENCES case_priorities(id),
  calculated_score            DECIMAL(4,2),
  calculated_sla_minutes      INTEGER,

  created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE (case_id, version)
);
CREATE INDEX ix_case_triages_case_id ON case_triages(case_id);
```

### 4.2 Tablas catálogo nuevas

```sql
CREATE TABLE triage_tool_types (
  id          VARCHAR(36) PRIMARY KEY,
  tenant_id   VARCHAR(36),                -- NULL = global
  name        VARCHAR(100) NOT NULL,
  description TEXT,
  is_active   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE triage_tool_actions (
  id            VARCHAR(36) PRIMARY KEY,
  tenant_id     VARCHAR(36),
  name          VARCHAR(50) NOT NULL,     -- Monitoreo|Bloqueo|...
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (tenant_id, name)
);
-- Renamed from `triage_tool_modes` per xlsx nomenclature ("Acción
-- aplicada", not "Modo herramienta"). Global list (not per-tool) because
-- the same actions apply across all tool types in the xlsx.

CREATE TABLE triage_sla_policies (
  id            VARCHAR(36) PRIMARY KEY,
  tenant_id     VARCHAR(36),
  priority_id   VARCHAR(36) NOT NULL REFERENCES case_priorities(id) ON DELETE CASCADE,
  sla_minutes   INTEGER,                  -- NULL = N/A (ej. Falso Positivo)
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (tenant_id, priority_id)
);
```

### 4.3 Reutilización de modelos existentes

- **`security_taxonomies`** ya tiene `internal_impact_context` /
  `external_impact_context` (Literal enum) y `parent_id` — directamente
  utilizables para el lookup automático de Impacto potencial.
- **`prioritization_*`** (formulas, criterions, scales, thresholds,
  case_priority_calculations) ya existen. Idealmente, el cálculo del
  triage usa una `PrioritizationFormula` específica (clave lógica
  `soc_triage_v1`) con los 3 criterios (severidad, impacto, criticidad
  activo) registrados como `PrioritizationCriterion`. Esto reutiliza la
  infraestructura de versionado + audit + recálculo existente.
- **`case_attachments`** ya soporta uploads; solo necesitamos 2 FKs en
  `case_triages` para distinguir semánticamente "evidencia" vs
  "comportamiento".

---

## 5. API surface (propuesta)

```
GET    /api/v1/cases/{case_id}/triage              # último triage del caso
GET    /api/v1/cases/{case_id}/triage/history      # todas las versiones
POST   /api/v1/cases/{case_id}/triage              # crear nueva versión
PUT    /api/v1/cases/{case_id}/triage/{triage_id}  # solo permitido si es la versión actual y < N minutos del create
```

POST/PUT internamente:
1. Valida que `case.taxonomy_id` esté asignado (sub-taxonomy debe pertenecer).
2. Resuelve Impacto potencial via lookup en sub-taxonomía.
3. Llama `PrioritizationUseCases.calculate(formula="soc_triage_v1", inputs=...)` →
   obtiene `priority_id` + `score`.
4. Lee `triage_sla_policies` para el `priority_id` → obtiene `sla_minutes`.
5. Persiste `case_triages` row + `case_priority_calculations` row.
6. Actualiza `case.priority_id` + `case.due_date` (o equivalente).
7. Emite evento `case.triage_completed` → AutomationEngine puede reaccionar
   (notificar, escalar, disparar n8n, etc.).

---

## 6. UI Triage (Fase 3)

### 6.1 Ubicación

Nuevo sub-tab **"Triage"** dentro de Seguridad (primero, antes de Wazuh Events).

### 6.2 Layout sugerido

```
┌─────────────────────────────────────────────────────────────────┐
│  ▌ Header DESCRIPCIÓN GENERAL (auto-fill, read-only)          │
│    Cliente · TLP · Fecha · Hora · Ofensa No.                   │
│    Identificación  | Notificación  | Duración notif | Contacto │
├─────────────────────────────────────────────────────────────────┤
│  ▌ Triage de la alerta                                         │
│    Título evento                                  [input]      │
│                                                                 │
│    Clasificación Incidente   [taxonomía padre  ▼ read-only]    │
│    Sub-clasificación         [taxonomía hijo   ▼ filtered]     │
│                                                                 │
│    Contexto Origen alerta    [tipo ▼] [detalle: input]         │
│    Activo relacionado        [input]                            │
│    Fuente del evento         [Tipo herramienta ▼] [Modo ▼]    │
│                                                                 │
│    NIVEL CRITICIDAD / PRIORIDAD       [calculado ▼ display]   │
│    Severidad de la alerta    [▼]                               │
│    Impacto potencial          [auto-derived ▼ display]         │
│    Criticidad de activo      [▼]                               │
│    Duración de la alerta     [hh:mm]                           │
│    Repeticiones              [int]                              │
├─────────────────────────────────────────────────────────────────┤
│  ▌ ANÁLISIS Y TRIAGE                                           │
│    [textarea grande]                                            │
│                                                                 │
│  ▌ EVIDENCIA DE LA ALERTA                                      │
│    [drop zone para imagen]                                      │
│                                                                 │
│  ▌ COMPORTAMIENTO Y RELACIÓN                                   │
│    [drop zone para imagen]                                      │
│    [textarea opcional]                                          │
│                                                                 │
│  ▌ RECOMENDACIONES                                             │
│    [textarea]                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                  [Cancelar]  [Guardar triage]  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 Validaciones

- Sub-clasificación es **obligatoria** (sin ella no se puede calcular Impacto).
- Severidad alerta + Criticidad activo son obligatorios (inputs de la matriz).
- Si el caso no tiene `taxonomy_id`: el tab no debería renderizarse
  (Fase 1 ya gatea esto).
- Cuando se cambia `Contexto Origen`, el campo Impacto potencial se
  actualiza inmediatamente (re-fetch / lookup local).
- Guardar muestra preview del cálculo de prioridad antes de confirmar.

---

## 7. Integración con Alert Report (Fase 4)

Los bloques existentes en
`backend/src/modules/alert_reports/templates/blocks/*.html` se actualizan
para leer del `case_triages` (último) cuando existe, con fallback al
comportamiento actual (lee de `cases` + notas) para reportes legacy:

| Bloque | Lee de `case_triages` |
|---|---|
| `alert_metadata.html` | snapshot del header + tool_type/mode |
| `triage_analysis.html` | `analysis_narrative` + sub-taxonomía + impacto |
| `evidence_grid.html` | `evidence_attachment_id` |
| `behavior_relation.html` | `behavior_attachment_id` + `behavior_narrative` |
| `recommendations.html` | `recommendations` |
| `priority_calculation.html` | `calculated_score` + matriz |

Cuando se genera el Alert Report, se snapshottea el triage actual al PDF.
Cambios posteriores al triage no afectan reportes ya emitidos (hash
SHA-256 preserva integridad).

---

## 8. Plan de implementación por fases

| Fase | Alcance | Tamaño estimado |
|---|---|---|
| **1 — Gate Seguridad tab** | Solo mostrar Seguridad si `case.taxonomy_id` | ✅ hecho (~15 líneas) |
| **2 — Backend triage** | Modelo + DTOs + use cases + endpoints + migration Alembic + seed catálogos `triage_tool_types`, `triage_tool_modes`, `triage_sla_policies`. Reutiliza `prioritization_*` para el cálculo. | ~600 líneas, 1 día |
| **3 — UI Triage tab** | Nuevo sub-tab + form + image upload + preview de cálculo + integración con `useCase` para refrescar prioridad post-save. | ~500 líneas, 1 día |
| **4 — Bloques Alert Report** | Modificar `*.html` para leer del triage; backwards-compat para casos sin triage. | ~100 líneas, 2-3 horas |
| **5 — UI Settings catálogos** | CRUD admin para `triage_tool_types`, `triage_tool_modes`, `triage_sla_policies`. | ~300 líneas, 4 horas |

Total estimado: **~2.5-3 días** de trabajo. Sugerido entregar por fase con
PR/review intermedio.

---

## 9. Preguntas abiertas (resolver antes de Fase 2)

- ¿El triage es **per-tenant** (cada tenant tiene su propio set de
  catálogos) o **global** (un solo set compartido)? Hoy las tablas
  parametrizables proponen `tenant_id` NULL = global, con override por
  tenant — patrón consistente con el resto del CMS.
- ¿Permisos? Sugerencia inicial:
  - `triage:read` — ver triage del caso
  - `triage:create` — crear primer triage de un caso
  - `triage:update_recent` — editar triage actual dentro de los primeros N min
  - `triage_catalogs:manage` — CRUD de catálogos en `/settings/triage-catalogs`
- ¿Se notifica al manager (taxonomy.managed_by_team_id) cuando un
  triage clasifica un evento como `Crítico`?
- ¿El recálculo de prioridad del triage debería **reemplazar** la
  prioridad auto-calculada original, o quedar como prioridad "manual"
  separada y mostrar ambas? Sugerencia: reemplaza, pero
  `case_priority_calculations` audita ambos cálculos con `trigger`
  diferente (`auto_create` vs `manual_triage`).

---

## 10. Origen de este documento

Spec capturada en sesión de diseño 2026-05-24 sobre conversación de
revisión de la pestaña Seguridad. Cambios futuros aquí deberían acompañar
las migraciones / PRs correspondientes para mantener doc + código en
sincro.

### 10.1 Revisión 2026-05-24 (post-import xlsx `Triage Eventos de Seguridad`)

Reconciliación con el documento operacional real del cliente (xlsx con
sheets `Triage`, `Priorización`, `Herramientas`, `Taxonomía v9`):

- §2.2: agregada nota sobre `Falso Positivo` como taxonomía válida (no
  solo severidad).
- §2.2.b: nueva sección con tabla TLP ↔ Criticidad ↔ Valoración derivada
  de `Priorización!R24-R28`.
- §2.3: rename `triage_tool_modes` → `triage_tool_actions` ("Acción
  aplicada" según xlsx). Lista de 15 herramientas confirmada con
  `NGFWG` (typo o intencional — preservar literal al importar).
- §3.2: `Falso Positivo` tratado como caso especial (skip matriz, prioridad
  directa = FP, SLA = N/A). Removido `Informativo` por no estar en xlsx.
- §4.1, §4.2: schema actualizado a `tool_action_id` / `triage_tool_actions`.

**Gap pendiente identificado** (NO en este doc, se resuelve aparte): el
seed actual de taxonomías CMS (`CODE-MALICIOUS`, `INTRUSION`, etc., ~20
rows) está desalineado con la `Taxonomía v9` del xlsx (~90 rows con
parents `Abuso de Contenido`, `Fraude`, `Seguridad del Contenido de la
Información`, `Violación de políticas`, `Falso Positivo`, etc.). Acción
acordada: script futuro `scripts/import_taxonomy_from_xlsx.py` que
soft-deletea taxonomías no presentes en xlsx y agrega las nuevas.
