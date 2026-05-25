"use client";

import { CheckCircle2, AlertTriangle, History } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useCase } from "@/hooks/useCases";
import { useSecurityTaxonomies } from "@/hooks/useSecurityTaxonomies";
import { useTriageCurrent, useCreateTriage } from "@/hooks/useTriage";
import {
  useTriageToolActions,
  useTriageToolTypes,
} from "@/hooks/useTriageCatalogs";
import type {
  AlertSeverity,
  AssetCriticality,
  ContextOriginType,
  CreateTriagePayload,
  SecurityTaxonomy,
} from "@/lib/types";
import { formatDate } from "@/lib/utils";

interface Props {
  caseId: string;
}

// ─── Static dropdowns ────────────────────────────────────────────

const SEVERITY_LEVELS: ReadonlyArray<readonly [AlertSeverity, string]> = [
  ["critico", "Crítico"],
  ["alto", "Alto"],
  ["medio", "Medio"],
  ["bajo", "Bajo"],
  ["falso_positivo", "Falso positivo"],
];

const CRITICALITY_LEVELS: ReadonlyArray<readonly [AssetCriticality, string]> = [
  ["critico", "Crítico"],
  ["alto", "Alto"],
  ["medio", "Medio"],
  ["bajo", "Bajo"],
];

const CONTEXT_ORIGIN_TYPES: ReadonlyArray<readonly [ContextOriginType, string]> = [
  ["origen_interno", "Origen Interno"],
  ["origen_externo", "Origen Externo"],
];

// Mirror of the backend matrix (see triage/application/use_cases.py).
// Duplicated here so the UI can preview the calculated priority/score
// in real time without a server round-trip. Keep in sync.
const LEVEL_VALUE: Record<string, number> = {
  critico: 5,
  alto: 4,
  medio: 3,
  bajo: 2,
};

function previewScore(
  severity: AlertSeverity,
  impactSlug: string | null,
  criticality: AssetCriticality,
): { score: number; priority: string } {
  if (severity === "falso_positivo") {
    return { score: 0, priority: "Falso Positivo" };
  }
  const sev = LEVEL_VALUE[severity] ?? 2;
  const imp = LEVEL_VALUE[impactSlug ?? "bajo"] ?? 2;
  const crit = LEVEL_VALUE[criticality] ?? 2;
  const score = sev * 0.5 + imp * 0.3 + crit * 0.2;
  let priority: string;
  if (score >= 4.5) priority = "Critica";
  else if (score >= 3.5) priority = "Alta";
  else if (score >= 2.5) priority = "Media";
  else priority = "Baja";
  return { score: Math.round(score * 100) / 100, priority };
}

// Backend stores impacts as slugs ("bajo"/"medio"/"alto"/"critico"/
// "falso_positivo"); display labels mirror Severity labels.
const IMPACT_LABEL: Record<string, string> = {
  bajo: "Bajo",
  medio: "Medio",
  alto: "Alto",
  critico: "Crítico",
  falso_positivo: "Falso positivo",
};

// ─── Main component ─────────────────────────────────────────────

export function TriageTab({ caseId }: Props) {
  const { data: caseData } = useCase(caseId);
  const { data: triageWithCtx } = useTriageCurrent(caseId);
  const { data: allTaxonomies = [] } = useSecurityTaxonomies();
  const { data: toolTypes = [] } = useTriageToolTypes();
  const { data: toolActions = [] } = useTriageToolActions();
  const create = useCreateTriage(caseId);

  // ── Form state ──────────────────────────────────────────────
  // Initialized from existing triage (if any) so the form acts as
  // "edit current" -- on save, backend creates a new versioned row.
  const [form, setForm] = useState<CreateTriagePayload>(() => ({
    sub_taxonomy_id: "",
    alert_severity: "medio",
    context_origin_type: "origen_interno",
    asset_criticality: "medio",
    tool_type_id: null,
    tool_action_id: null,
    context_origin_detail: "",
    related_asset: "",
    alert_duration_seconds: null,
    alert_repetitions: 1,
    analysis_narrative: "",
    behavior_narrative: "",
    recommendations: "",
    evidence_attachment_id: null,
    behavior_attachment_id: null,
  }));
  const [durationHHMM, setDurationHHMM] = useState("");

  // Hydrate from existing triage on first load (or when it changes
  // because a new revision was created externally).
  useEffect(() => {
    if (!triageWithCtx) return;
    const t = triageWithCtx.triage;
    setForm({
      sub_taxonomy_id: t.sub_taxonomy_id,
      alert_severity: t.alert_severity,
      context_origin_type: t.context_origin_type,
      asset_criticality: t.asset_criticality,
      tool_type_id: t.tool_type_id,
      tool_action_id: t.tool_action_id,
      context_origin_detail: t.context_origin_detail ?? "",
      related_asset: t.related_asset ?? "",
      alert_duration_seconds: t.alert_duration_seconds,
      alert_repetitions: t.alert_repetitions,
      analysis_narrative: t.analysis_narrative ?? "",
      behavior_narrative: t.behavior_narrative ?? "",
      recommendations: t.recommendations ?? "",
      evidence_attachment_id: t.evidence_attachment_id,
      behavior_attachment_id: t.behavior_attachment_id,
    });
    if (t.alert_duration_seconds != null) {
      const hh = Math.floor(t.alert_duration_seconds / 3600);
      const mm = Math.floor((t.alert_duration_seconds % 3600) / 60);
      setDurationHHMM(
        `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`,
      );
    }
  }, [triageWithCtx]);

  // ── Derived data ────────────────────────────────────────────

  // case.taxonomy_id can point to EITHER a parent (root) OR a sub. In
  // our depth-2 hierarchy, if the linked taxonomy has a parent_id, then
  // it's a sub and we walk up one level for the parent. Otherwise it IS
  // the parent. This matters because taxonomy_catalog_mappings often
  // points the catalog directly at the sub (e.g. SPAM under "Abuso de
  // Contenido"), not at the root.
  const linkedTaxonomy = useMemo<SecurityTaxonomy | undefined>(() => {
    if (!caseData?.taxonomy_id) return undefined;
    return allTaxonomies.find((t) => t.id === caseData.taxonomy_id);
  }, [caseData?.taxonomy_id, allTaxonomies]);

  const parentTaxonomy = useMemo<SecurityTaxonomy | undefined>(() => {
    if (!linkedTaxonomy) return undefined;
    if (linkedTaxonomy.parent_id) {
      // Linked taxonomy is a sub -- find its parent
      return allTaxonomies.find((t) => t.id === linkedTaxonomy.parent_id);
    }
    // Already a root
    return linkedTaxonomy;
  }, [linkedTaxonomy, allTaxonomies]);

  // Pre-fill sub_taxonomy_id from the case's linked taxonomy when it
  // IS a sub (most common via catalog mapping). The user can still
  // override via the dropdown if the original classification was wrong.
  const suggestedSubId = useMemo<string | null>(() => {
    if (!linkedTaxonomy) return null;
    // Only suggest if the linked one is itself a sub (has parent_id).
    return linkedTaxonomy.parent_id ? linkedTaxonomy.id : null;
  }, [linkedTaxonomy]);

  // Apply the suggestion exactly once when the case loads (and only when
  // the user hasn't yet picked a sub manually + there's no existing
  // triage already hydrating the form).
  useEffect(() => {
    if (!suggestedSubId) return;
    if (form.sub_taxonomy_id) return;     // user picked OR triage hydrated
    if (triageWithCtx) return;            // existing triage takes precedence
    setForm((f) => ({ ...f, sub_taxonomy_id: suggestedSubId }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestedSubId, triageWithCtx]);

  const subTaxonomies = useMemo<SecurityTaxonomy[]>(() => {
    if (!parentTaxonomy) return [];
    return allTaxonomies
      .filter((t) => t.parent_id === parentTaxonomy.id && t.is_active)
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [allTaxonomies, parentTaxonomy]);

  const selectedSub = useMemo<SecurityTaxonomy | undefined>(() => {
    return subTaxonomies.find((s) => s.id === form.sub_taxonomy_id);
  }, [subTaxonomies, form.sub_taxonomy_id]);

  // Impact potencial auto-derived from selected sub + origin context
  const impactSlug = useMemo<string | null>(() => {
    if (!selectedSub) return null;
    if (form.context_origin_type === "origen_interno") {
      return selectedSub.internal_impact_context;
    }
    return selectedSub.external_impact_context;
  }, [selectedSub, form.context_origin_type]);

  // Live priority + score preview (mirrors backend matrix)
  const preview = useMemo(
    () =>
      previewScore(
        form.alert_severity,
        impactSlug,
        form.asset_criticality,
      ),
    [form.alert_severity, impactSlug, form.asset_criticality],
  );

  // Parse hh:mm duration into seconds
  function handleDurationChange(value: string) {
    setDurationHHMM(value);
    const m = value.match(/^(\d{1,2}):(\d{2})$/);
    if (m) {
      const seconds = Number(m[1]) * 3600 + Number(m[2]) * 60;
      setForm((f) => ({ ...f, alert_duration_seconds: seconds }));
    } else if (value === "") {
      setForm((f) => ({ ...f, alert_duration_seconds: null }));
    }
  }

  async function handleSave() {
    if (!form.sub_taxonomy_id) return;
    try {
      await create.mutateAsync(form);
    } catch {
      // mutation.error renders below
    }
  }

  // ── Guards ──────────────────────────────────────────────────

  if (!caseData?.taxonomy_id) {
    return (
      <div className="rounded border border-dashed p-6 text-sm text-muted-foreground">
        Este caso no tiene taxonomía asignada — el triage requiere una
        clasificación. Asigná una taxonomía desde el panel Detalles antes de
        triagear.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* ── Header auto-fill ──────────────────────────────── */}
      <section className="rounded border bg-muted/40 p-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Descripción general de la gestión de la alerta
        </p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
          <Field label="Cliente" value={triageWithCtx?.triage.case_tenant_name_snapshot ?? "—"} />
          <Field label="TLP" value={parentTaxonomy?.tlp_default?.toUpperCase() ?? "—"} />
          <Field label="Caso #" value={caseData.case_number} />
          <Field label="Fecha" value={formatDate(caseData.created_at)} />
          <Field
            label="Notificado por"
            value={
              caseData.created_by_name
                ? caseData.created_by_email
                  ? `${caseData.created_by_name} (${caseData.created_by_email})`
                  : caseData.created_by_name
                : "—"
            }
          />
          <Field label="Tipo de caso" value={caseData.case_type ?? "—"} />
          <Field label="Estado" value={caseData.status_name} />
          <Field label="Versión triage" value={triageWithCtx ? `v${triageWithCtx.triage.version}` : "Nueva"} />
        </div>
      </section>

      {/* ── Classification ────────────────────────────────── */}
      <section className="rounded border p-3 space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Clasificación
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Static label="Clasificación Incidente (padre)" value={parentTaxonomy?.name ?? "—"} />
          <Dropdown
            label="Sub-clasificación"
            required
            value={form.sub_taxonomy_id}
            onChange={(v) => setForm((f) => ({ ...f, sub_taxonomy_id: v }))}
            options={[
              { value: "", label: "— elegir sub-clasificación —" },
              ...subTaxonomies.map((s) => ({ value: s.id, label: s.name })),
            ]}
          />
          <Dropdown
            label="Contexto Origen alerta"
            value={form.context_origin_type}
            onChange={(v) =>
              setForm((f) => ({ ...f, context_origin_type: v as ContextOriginType }))
            }
            options={CONTEXT_ORIGIN_TYPES.map(([v, l]) => ({ value: v, label: l }))}
          />
          <Input
            label="Detalle origen (IP / Red / Correo)"
            value={form.context_origin_detail ?? ""}
            onChange={(v) =>
              setForm((f) => ({ ...f, context_origin_detail: v }))
            }
          />
          <Input
            label="Activo relacionado (IP / Red / Activo)"
            value={form.related_asset ?? ""}
            onChange={(v) => setForm((f) => ({ ...f, related_asset: v }))}
          />
          <Static
            label="Título del caso"
            value={caseData.title}
          />
        </div>
      </section>

      {/* ── Source tool ───────────────────────────────────── */}
      <section className="rounded border p-3 space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Fuente del evento
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Dropdown
            label="Tipo de herramienta"
            value={form.tool_type_id ?? ""}
            onChange={(v) =>
              setForm((f) => ({ ...f, tool_type_id: v || null }))
            }
            options={[
              { value: "", label: "— sin asignar —" },
              ...toolTypes.map((t) => ({ value: t.id, label: t.name })),
            ]}
          />
          <Dropdown
            label="Acción aplicada"
            value={form.tool_action_id ?? ""}
            onChange={(v) =>
              setForm((f) => ({ ...f, tool_action_id: v || null }))
            }
            options={[
              { value: "", label: "— sin asignar —" },
              ...toolActions.map((a) => ({ value: a.id, label: a.name })),
            ]}
          />
        </div>
      </section>

      {/* ── Matrix inputs + live priority preview ─────────── */}
      <section className="rounded border p-3 space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Matriz de criticidad
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Dropdown
            label="Severidad de la alerta (50%)"
            value={form.alert_severity}
            onChange={(v) =>
              setForm((f) => ({ ...f, alert_severity: v as AlertSeverity }))
            }
            options={SEVERITY_LEVELS.map(([v, l]) => ({ value: v, label: l }))}
          />
          <Static
            label="Impacto potencial (30%)"
            value={impactSlug ? IMPACT_LABEL[impactSlug] ?? impactSlug : "—"}
            hint="Auto-derivado de sub-clasificación + contexto origen"
          />
          <Dropdown
            label="Criticidad de activo (20%)"
            value={form.asset_criticality}
            onChange={(v) =>
              setForm((f) => ({ ...f, asset_criticality: v as AssetCriticality }))
            }
            options={CRITICALITY_LEVELS.map(([v, l]) => ({ value: v, label: l }))}
          />
          <Input
            label="Duración (hh:mm)"
            value={durationHHMM}
            onChange={handleDurationChange}
            placeholder="00:30"
          />
          <Input
            label="Repeticiones"
            type="number"
            value={String(form.alert_repetitions)}
            onChange={(v) =>
              setForm((f) => ({ ...f, alert_repetitions: Number(v) || 1 }))
            }
          />
          <PriorityPreview score={preview.score} priority={preview.priority} />
        </div>
      </section>

      {/* ── Narratives ────────────────────────────────────── */}
      <section className="rounded border p-3 space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Análisis y triage
        </p>
        <Textarea
          label="Descripción del análisis"
          value={form.analysis_narrative ?? ""}
          onChange={(v) =>
            setForm((f) => ({ ...f, analysis_narrative: v }))
          }
          rows={4}
          placeholder="Describir los hechos: qué, cómo, cuándo, hipótesis, impacto potencial"
        />
        <Textarea
          label="Comportamiento y relación con otras alertas"
          value={form.behavior_narrative ?? ""}
          onChange={(v) =>
            setForm((f) => ({ ...f, behavior_narrative: v }))
          }
          rows={3}
        />
        <Textarea
          label="Recomendaciones"
          value={form.recommendations ?? ""}
          onChange={(v) => setForm((f) => ({ ...f, recommendations: v }))}
          rows={3}
        />
        <p className="text-[11px] text-muted-foreground">
          📎 Adjuntar evidencia + screenshot de comportamiento: usá la
          pestaña Adjuntos y referencialos al guardar el triage
          (próxima iteración wireará los selectores aquí mismo).
        </p>
      </section>

      {/* ── Error + save bar ──────────────────────────────── */}
      {create.isError && (
        <p className="rounded bg-rose-50 px-3 py-2 text-sm text-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
          {(create.error as Error).message}
        </p>
      )}

      {triageWithCtx && (
        <div className="flex items-center gap-2 rounded bg-emerald-50 px-3 py-2 text-xs text-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">
          <History className="h-3.5 w-3.5" />
          Triage actual: v{triageWithCtx.triage.version} —{" "}
          {formatDate(triageWithCtx.triage.triaged_at)}
          {triageWithCtx.triage.calculated_score && (
            <>
              {" · "}score {triageWithCtx.triage.calculated_score}
            </>
          )}
        </div>
      )}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSave}
          disabled={!form.sub_taxonomy_id || create.isPending}
          className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {create.isPending
            ? "Guardando…"
            : triageWithCtx
              ? `Crear revisión v${triageWithCtx.triage.version + 1}`
              : "Guardar triage"}
        </button>
      </div>
    </div>
  );
}

// ─── UI atoms (local; small enough not to extract) ───────────────

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase text-muted-foreground">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  );
}

function Static({
  label, value, hint,
}: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <label className="text-[11px] text-muted-foreground">{label}</label>
      <div className="rounded border bg-muted/30 px-2 py-1.5 text-sm">
        {value}
      </div>
      {hint && (
        <p className="text-[10px] text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}

function Input({
  label, value, onChange, type = "text", placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <label className="text-[11px] text-muted-foreground">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="rounded border bg-background px-2 py-1.5 text-sm"
      />
    </div>
  );
}

function Textarea({
  label, value, onChange, rows = 3, placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  placeholder?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <label className="text-[11px] text-muted-foreground">{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        placeholder={placeholder}
        className="rounded border bg-background px-2 py-1.5 text-sm"
      />
    </div>
  );
}

function Dropdown({
  label, value, onChange, options, required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  required?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <label className="text-[11px] text-muted-foreground">
        {label}
        {required && <span className="text-rose-600"> *</span>}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border bg-background px-2 py-1.5 text-sm"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

function PriorityPreview({ score, priority }: { score: number; priority: string }) {
  const color =
    priority === "Critica" ? "bg-rose-100 text-rose-900 dark:bg-rose-950/40 dark:text-rose-200"
    : priority === "Alta"   ? "bg-orange-100 text-orange-900 dark:bg-orange-950/40 dark:text-orange-200"
    : priority === "Media"  ? "bg-amber-100 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
    : priority === "Baja"   ? "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
    : "bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-200";
  const Icon = priority === "Critica" || priority === "Alta" ? AlertTriangle : CheckCircle2;
  return (
    <div className="flex flex-col gap-0.5">
      <label className="text-[11px] text-muted-foreground">
        Prioridad calculada (preview)
      </label>
      <div className={`flex items-center gap-2 rounded border px-2 py-1.5 text-sm font-medium ${color}`}>
        <Icon className="h-4 w-4" />
        {priority} · score {score.toFixed(2)}
      </div>
    </div>
  );
}
