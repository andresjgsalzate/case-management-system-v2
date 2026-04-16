"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Zap, GitBranch, ToggleLeft, ToggleRight, Plus, Trash2,
  Pencil, X, Save, ChevronDown, ChevronUp, AlertCircle,
} from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Badge } from "@/components/atoms/Badge";
import { Spinner } from "@/components/atoms/Spinner";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import { formatDate } from "@/lib/utils";
import { useCasePriorities, useCaseStatuses, useUsers } from "@/hooks/useCases";
import type { ApiResponse } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Condition {
  field: string;
  operator: string;
  value: string;
}

interface Action {
  action_type: string;
  params: Record<string, string>;
}

interface AutomationRule {
  id: string;
  name: string;
  description?: string;
  trigger_event: string;
  conditions: Condition[];
  actions: Action[];
  condition_logic: "AND" | "OR";
  is_active: boolean;
  execution_count: number;
  created_at: string;
}

// ── Catalog ───────────────────────────────────────────────────────────────────

const EVENT_LABELS: Record<string, string> = {
  "case.created":          "Caso creado",
  "case.status_changed":   "Estado cambiado",
  "case.assigned":         "Caso asignado",
  "case.priority_changed": "Prioridad cambiada",
  "sla.breached":          "SLA incumplido",
  "schedule.daily":        "Programado (diario)",
  "case.closed":           "Caso cerrado",
  "resolution.responded":  "Solicitante respondió",
  "todo.completed":        "Tarea completada",
  "attachment.uploaded":   "Archivo adjunto",
  "note.created":          "Nota agregada",
};

const CONDITION_FIELDS: Record<string, { label: string; valueType: "priority" | "status" | "text" }> = {
  priority_id:          { label: "Prioridad",          valueType: "priority" },
  status_id:            { label: "Estado",              valueType: "status" },
};

const OPERATORS: Record<string, string> = {
  equals:     "es igual a",
  not_equals: "no es igual a",
};

const ACTION_TYPES: Record<string, string> = {
  send_notification:    "Enviar notificación",
  change_priority:      "Cambiar prioridad",
  assign_agent:         "Asignar a agente",
  archive_closed_cases: "Archivar casos cerrados",
  change_status:        "Cambiar estado",
  create_todo:          "Crear tarea",
  escalate_priority:    "Escalar prioridad",
};

// ── Hooks ─────────────────────────────────────────────────────────────────────

function useAutomationRules() {
  return useQuery({
    queryKey: ["automation-rules"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<AutomationRule[]>>(
        "/automation/rules?active_only=false"
      );
      return data.data ?? [];
    },
  });
}

// ── Blank form ────────────────────────────────────────────────────────────────

function blankForm(): Omit<AutomationRule, "id" | "is_active" | "execution_count" | "created_at"> {
  return {
    name: "",
    description: "",
    trigger_event: "case.created",
    condition_logic: "AND",
    conditions: [],
    actions: [],
  };
}

function ruleToForm(rule: AutomationRule) {
  return {
    name: rule.name,
    description: rule.description ?? "",
    trigger_event: rule.trigger_event,
    condition_logic: rule.condition_logic,
    conditions: rule.conditions as Condition[],
    actions: rule.actions as Action[],
  };
}

// ── Condition row ─────────────────────────────────────────────────────────────

function ConditionRow({
  cond,
  onChange,
  onRemove,
  priorities,
  statuses,
}: {
  cond: Condition;
  onChange: (c: Condition) => void;
  onRemove: () => void;
  priorities: { id: string; name: string }[];
  statuses: { id: string; name: string }[];
}) {
  const fieldMeta = CONDITION_FIELDS[cond.field];

  return (
    <div className="flex items-start gap-2 p-3 rounded-md bg-muted/40 border border-border">
      {/* Field */}
      <select
        className="flex-1 px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
        value={cond.field}
        onChange={(e) => onChange({ ...cond, field: e.target.value, value: "" })}
      >
        <option value="">— campo —</option>
        {Object.entries(CONDITION_FIELDS).map(([val, meta]) => (
          <option key={val} value={val}>{meta.label}</option>
        ))}
      </select>

      {/* Operator */}
      <select
        className="flex-1 px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
        value={cond.operator}
        onChange={(e) => onChange({ ...cond, operator: e.target.value })}
      >
        {Object.entries(OPERATORS).map(([val, label]) => (
          <option key={val} value={val}>{label}</option>
        ))}
      </select>

      {/* Value — smart based on field type */}
      {fieldMeta?.valueType === "priority" && (
        <select
          className="flex-1 px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          value={cond.value}
          onChange={(e) => onChange({ ...cond, value: e.target.value })}
        >
          <option value="">— prioridad —</option>
          {priorities.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      )}
      {fieldMeta?.valueType === "status" && (
        <select
          className="flex-1 px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          value={cond.value}
          onChange={(e) => onChange({ ...cond, value: e.target.value })}
        >
          <option value="">— estado —</option>
          {statuses.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      )}
      {!fieldMeta && (
        <input
          className="flex-1 px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          placeholder="valor"
          value={cond.value}
          onChange={(e) => onChange({ ...cond, value: e.target.value })}
        />
      )}

      <button
        type="button"
        onClick={onRemove}
        className="p-1.5 text-muted-foreground hover:text-destructive transition-colors shrink-0"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

// ── Action row ────────────────────────────────────────────────────────────────

function ActionRow({
  action,
  onChange,
  onRemove,
  priorities,
  users,
}: {
  action: Action;
  onChange: (a: Action) => void;
  onRemove: () => void;
  priorities: { id: string; name: string }[];
  users: { id: string; full_name: string }[];
}) {
  function setParam(key: string, value: string) {
    onChange({ ...action, params: { ...action.params, [key]: value } });
  }

  return (
    <div className="flex flex-col gap-2 p-3 rounded-md bg-muted/40 border border-border">
      <div className="flex items-center gap-2">
        {/* Action type */}
        <select
          className="flex-1 px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          value={action.action_type}
          onChange={(e) => {
            const type = e.target.value;
            const defaultParams: Record<string, string> =
              type === "archive_closed_cases" ? { days_after_close: "30" }
              : type === "create_todo"        ? { title: "" }
              : {};
            onChange({ action_type: type, params: defaultParams });
          }}
        >
          <option value="">— tipo de acción —</option>
          {Object.entries(ACTION_TYPES).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
        <button
          type="button"
          onClick={onRemove}
          className="p-1.5 text-muted-foreground hover:text-destructive transition-colors shrink-0"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Params for send_notification */}
      {action.action_type === "send_notification" && (
        <div className="flex flex-col gap-2 pl-1">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Destinatario</label>
            <select
              className="px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
              value={action.params.user_id ?? ""}
              onChange={(e) => setParam("user_id", e.target.value)}
            >
              <option value="">— seleccionar usuario —</option>
              {users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Título de la notificación</label>
            <input
              className="px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="Ej: SLA Incumplido"
              value={action.params.title ?? ""}
              onChange={(e) => setParam("title", e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Mensaje</label>
            <textarea
              rows={2}
              className="px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary resize-none"
              placeholder="Ej: Un caso ha superado el tiempo límite del SLA"
              value={action.params.body ?? ""}
              onChange={(e) => setParam("body", e.target.value)}
            />
          </div>
        </div>
      )}

      {/* Params for change_priority */}
      {action.action_type === "change_priority" && (
        <div className="pl-1">
          <label className="text-xs text-muted-foreground">Nueva prioridad</label>
          <select
            className="mt-1 w-full px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
            value={action.params.priority_id ?? ""}
            onChange={(e) => setParam("priority_id", e.target.value)}
          >
            <option value="">— seleccionar prioridad —</option>
            {priorities.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
      )}

      {/* Params for assign_agent */}
      {action.action_type === "assign_agent" && (
        <div className="pl-1">
          <label className="text-xs text-muted-foreground">Agente a asignar</label>
          <select
            className="mt-1 w-full px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
            value={action.params.agent_id ?? ""}
            onChange={(e) => setParam("agent_id", e.target.value)}
          >
            <option value="">— seleccionar agente —</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </select>
        </div>
      )}

      {/* Params for archive_closed_cases */}
      {action.action_type === "archive_closed_cases" && (
        <div className="pl-1">
          <label className="text-xs text-muted-foreground">Días desde el cierre</label>
          <input
            type="number"
            min={1}
            max={365}
            className="mt-1 w-32 px-2 py-1.5 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
            value={action.params.days_after_close ?? "30"}
            onChange={(e) => setParam("days_after_close", e.target.value)}
          />
        </div>
      )}

      {/* Params for change_status */}
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

      {/* Params for create_todo */}
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

      {/* Params for escalate_priority */}
      {action.action_type === "escalate_priority" && (
        <p className="pl-1 text-xs text-muted-foreground">
          Sube la prioridad del caso un nivel. Si ya está en el nivel más alto, no hace nada.
        </p>
      )}
    </div>
  );
}

// ── Types ─────────────────────────────────────────────────────────────────────

type FormState = ReturnType<typeof blankForm>;

// ── Rule editor (create + edit) ───────────────────────────────────────────────;

function RuleEditor({
  initial,
  onSave,
  onCancel,
  isPending,
  error,
  isEdit,
}: {
  initial: FormState;
  onSave: (form: FormState) => void;
  onCancel: () => void;
  isPending: boolean;
  error: string;
  isEdit: boolean;
}) {
  const [form, setForm] = useState<FormState>(initial);
  const { data: priorities = [] } = useCasePriorities();
  const { data: statuses = [] } = useCaseStatuses();
  const { data: users = [] } = useUsers();

  function addCondition() {
    setForm((f) => ({
      ...f,
      conditions: [...f.conditions, { field: "priority_id", operator: "equals", value: "" }],
    }));
  }

  function updateCondition(i: number, cond: Condition) {
    setForm((f) => {
      const next = [...f.conditions];
      next[i] = cond;
      return { ...f, conditions: next };
    });
  }

  function removeCondition(i: number) {
    setForm((f) => ({ ...f, conditions: f.conditions.filter((_, idx) => idx !== i) }));
  }

  function addAction() {
    setForm((f) => ({
      ...f,
      actions: [...f.actions, { action_type: "send_notification", params: {} }],
    }));
  }

  function updateAction(i: number, action: Action) {
    setForm((f) => {
      const next = [...f.actions];
      next[i] = action;
      return { ...f, actions: next };
    });
  }

  function removeAction(i: number) {
    setForm((f) => ({ ...f, actions: f.actions.filter((_, idx) => idx !== i) }));
  }

  const canSave = form.name.trim() && form.actions.length > 0;

  return (
    <div className="rounded-lg border border-primary/30 bg-card p-5 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground">
          {isEdit ? "Editar regla de automatización" : "Nueva regla de automatización"}
        </p>
        <button type="button" onClick={onCancel} className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-xs text-destructive bg-destructive/5 border border-destructive/20 rounded-md px-3 py-2">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          {error}
        </div>
      )}

      {/* ── Información básica ── */}
      <section className="flex flex-col gap-3">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Información</p>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2 flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Nombre <span className="text-destructive">*</span></label>
            <input
              className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="Ej: Notificar cuando SLA incumpla"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div className="col-span-2 flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Descripción</label>
            <input
              className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="Qué hace esta regla…"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
        </div>
      </section>

      {/* ── Disparador ── */}
      <section className="flex flex-col gap-3">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Disparador</p>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">Evento que activa la regla <span className="text-destructive">*</span></label>
          <select
            className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
            value={form.trigger_event}
            onChange={(e) => setForm((f) => ({ ...f, trigger_event: e.target.value }))}
          >
            {Object.entries(EVENT_LABELS).map(([val, label]) => (
              <option key={val} value={val}>{label}</option>
            ))}
          </select>
        </div>
      </section>

      {/* ── Condiciones ── */}
      {form.trigger_event !== "schedule.daily" && (
        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Condiciones</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Si no hay condiciones, la regla se activa en todos los casos del evento.
              </p>
            </div>
            {form.conditions.length > 1 && (
              <select
                className="px-2 py-1 text-xs rounded-md border border-border bg-background focus:outline-none"
                value={form.condition_logic}
                onChange={(e) => setForm((f) => ({ ...f, condition_logic: e.target.value as "AND" | "OR" }))}
              >
                <option value="AND">Todas deben cumplirse (AND)</option>
                <option value="OR">Alguna debe cumplirse (OR)</option>
              </select>
            )}
          </div>

          <div className="flex flex-col gap-2">
            {form.conditions.map((cond, i) => (
              <ConditionRow
                key={i}
                cond={cond}
                onChange={(c) => updateCondition(i, c)}
                onRemove={() => removeCondition(i)}
                priorities={priorities}
                statuses={statuses}
              />
            ))}
          </div>

          <button
            type="button"
            onClick={addCondition}
            className="self-start flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border border-dashed border-border hover:border-primary/50 text-muted-foreground hover:text-foreground transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Agregar condición
          </button>
        </section>
      )}

      {/* ── Acciones ── */}
      <section className="flex flex-col gap-3">
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Acciones <span className="text-destructive">*</span>
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Qué hace el sistema cuando se activa la regla.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          {form.actions.map((action, i) => (
            <ActionRow
              key={i}
              action={action}
              onChange={(a) => updateAction(i, a)}
              onRemove={() => removeAction(i)}
              priorities={priorities}
              users={users}
            />
          ))}
        </div>

        {form.actions.length === 0 && (
          <p className="text-xs text-destructive">Debes agregar al menos una acción.</p>
        )}

        <button
          type="button"
          onClick={addAction}
          className="self-start flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border border-dashed border-border hover:border-primary/50 text-muted-foreground hover:text-foreground transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Agregar acción
        </button>
      </section>

      {/* ── Footer ── */}
      <div className="flex gap-2 justify-end border-t border-border pt-4">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Cancelar
        </button>
        <button
          type="button"
          disabled={!canSave || isPending}
          onClick={() => onSave(form)}
          className="flex items-center gap-2 px-4 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Save className="h-4 w-4" />
          {isPending ? "Guardando…" : isEdit ? "Guardar cambios" : "Crear regla"}
        </button>
      </div>
    </div>
  );
}

// ── Rule card ─────────────────────────────────────────────────────────────────

function actionSummary(actions: Action[]): string {
  return actions
    .map((a) => ACTION_TYPES[a.action_type] ?? a.action_type)
    .join(", ") || "Sin acciones";
}

function RuleCard({
  rule,
  onEdit,
  onToggle,
  onDelete,
}: {
  rule: AutomationRule;
  onEdit: () => void;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="p-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className="h-9 w-9 rounded-md bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
            <Zap className="h-4 w-4 text-primary" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-foreground">{rule.name}</span>
              <Badge variant={rule.is_active ? "success" : "outline"} className="text-xs">
                {rule.is_active ? "Activa" : "Inactiva"}
              </Badge>
            </div>
            {rule.description && (
              <p className="text-xs text-muted-foreground mt-0.5 truncate">{rule.description}</p>
            )}
            <div className="flex flex-wrap gap-3 mt-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <GitBranch className="h-3 w-3" />
                {EVENT_LABELS[rule.trigger_event] ?? rule.trigger_event}
              </span>
              <span>
                {rule.conditions.length
                  ? `${rule.conditions.length} condición${rule.conditions.length !== 1 ? "es" : ""} (${rule.condition_logic})`
                  : "Sin condiciones"}
              </span>
              <span>{actionSummary(rule.actions)}</span>
              <span>{rule.execution_count} ejecución{rule.execution_count !== 1 ? "es" : ""}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={onEdit}
            title="Editar"
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onToggle}
            title={rule.is_active ? "Desactivar" : "Activar"}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            {rule.is_active
              ? <ToggleRight className="h-5 w-5 text-primary" />
              : <ToggleLeft className="h-5 w-5" />}
          </button>
          <button
            type="button"
            onClick={onDelete}
            title="Eliminar"
            className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/5 transition-colors"
          >
            <Trash2 className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            title="Ver detalles"
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-border px-4 py-3 flex flex-col gap-3">
          {rule.conditions.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">
                Condiciones ({rule.condition_logic})
              </p>
              {rule.conditions.map((c, i) => (
                <p key={i} className="text-xs text-foreground font-mono bg-muted/50 px-2 py-1 rounded mb-1">
                  {CONDITION_FIELDS[c.field]?.label ?? c.field} {OPERATORS[c.operator] ?? c.operator} <span className="text-primary">{c.value}</span>
                </p>
              ))}
            </div>
          )}
          {rule.actions.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">Acciones</p>
              {rule.actions.map((a, i) => (
                <p key={i} className="text-xs text-foreground bg-muted/50 px-2 py-1 rounded mb-1">
                  <span className="font-medium">{ACTION_TYPES[a.action_type] ?? a.action_type}</span>
                  {a.params.title && <span className="text-muted-foreground"> — {a.params.title}</span>}
                  {a.params.priority_id && <span className="text-muted-foreground"> — ID: {a.params.priority_id}</span>}
                  {a.params.agent_id && <span className="text-muted-foreground"> — ID: {a.params.agent_id}</span>}
                </p>
              ))}
            </div>
          )}
          <p className="text-xs text-muted-foreground">Creada {formatDate(rule.created_at)}</p>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AutomationSettingsPage() {
  const confirm = useConfirm();
  const qc = useQueryClient();
  const { data: rules = [], isLoading } = useAutomationRules();

  // editorState: null = hidden, "create" = new rule, string = rule id being edited
  const [editorState, setEditorState] = useState<null | "create" | string>(null);
  const [editorError, setEditorError] = useState("");

  const editingRule = typeof editorState === "string" && editorState !== "create"
    ? rules.find((r) => r.id === editorState)
    : undefined;

  const createMutation = useMutation({
    mutationFn: (body: FormState) => apiClient.post("/automation/rules", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automation-rules"] });
      setEditorState(null);
      setEditorError("");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setEditorError(msg ?? "Error al crear regla");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: FormState }) =>
      apiClient.patch(`/automation/rules/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automation-rules"] });
      setEditorState(null);
      setEditorError("");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setEditorError(msg ?? "Error al guardar cambios");
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (id: string) => apiClient.post(`/automation/rules/${id}/toggle`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["automation-rules"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/automation/rules/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["automation-rules"] }),
  });

  function openCreate() {
    setEditorState("create");
    setEditorError("");
  }

  function openEdit(rule: AutomationRule) {
    setEditorState(rule.id);
    setEditorError("");
  }

  function closeEditor() {
    setEditorState(null);
    setEditorError("");
  }

  async function handleDelete(id: string, name: string) {
    const ok = await confirm({
      title: "¿Eliminar regla?",
      description: `Se eliminará "${name}". Esta acción no se puede deshacer.`,
      confirmLabel: "Eliminar",
    });
    if (ok) deleteMutation.mutate(id);
  }

  type FormState = ReturnType<typeof blankForm>;

  function handleSave(form: FormState) {
    if (editorState === "create") {
      createMutation.mutate(form);
    } else if (editorState) {
      updateMutation.mutate({ id: editorState, body: form });
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Automatización</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isLoading ? "Cargando…" : `${rules.length} regla${rules.length !== 1 ? "s" : ""} configuradas`}
          </p>
        </div>
        {editorState === null && (
          <button
            type="button"
            onClick={openCreate}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Nueva regla
          </button>
        )}
      </div>

      {/* Editor */}
      {editorState !== null && (
        <RuleEditor
          initial={editorState === "create" ? blankForm() : ruleToForm(editingRule ?? rules[0])}
          onSave={handleSave}
          onCancel={closeEditor}
          isPending={isSaving}
          error={editorError}
          isEdit={editorState !== "create"}
        />
      )}

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!isLoading && rules.length === 0 && editorState === null && (
        <div className="rounded-lg border border-border bg-card p-8 text-center">
          <Zap className="h-8 w-8 mx-auto mb-2 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">No hay reglas de automatización</p>
          <p className="text-xs text-muted-foreground mt-1">
            Las reglas ejecutan acciones automáticas ante eventos del sistema
          </p>
          <button
            type="button"
            onClick={openCreate}
            className="mt-3 flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-dashed border-border hover:border-primary/40 text-muted-foreground hover:text-foreground transition-colors mx-auto"
          >
            <Plus className="h-4 w-4" />
            Crear primera regla
          </button>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {rules.map((rule) => (
          <RuleCard
            key={rule.id}
            rule={rule}
            onEdit={() => openEdit(rule)}
            onToggle={() => toggleMutation.mutate(rule.id)}
            onDelete={() => handleDelete(rule.id, rule.name)}
          />
        ))}
      </div>
    </div>
  );
}
