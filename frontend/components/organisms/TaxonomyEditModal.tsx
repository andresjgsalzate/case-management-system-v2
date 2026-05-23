"use client";

import { Plus, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/atoms/Button";
import { MitreTechniquePickerModal } from "@/components/organisms/MitreTechniquePickerModal";
import {
  useMitreTechniquesByIds,
} from "@/hooks/useMitreTechniques";
import { useN8nWorkflows } from "@/hooks/useN8nWorkflows";
import {
  useCreateTaxonomy,
  useUpdateTaxonomy,
} from "@/hooks/useSecurityTaxonomies";
import type {
  CreateTaxonomyPayload,
  SecurityTaxonomy,
  TLP,
  TaxonomyDefaultCaseType,
  TriageMode,
  UpdateTaxonomyPayload,
} from "@/lib/types";
import { cn } from "@/lib/utils";

// Mirrors backend `ImpactLevel` Literal (dtos.py).
// Tuple of [slug stored in DB, human label rendered in the picker].
const IMPACT_LEVELS: ReadonlyArray<readonly [string, string]> = [
  ["bajo", "Bajo"],
  ["medio", "Medio"],
  ["alto", "Alto"],
  ["critico", "Crítico"],
  ["informativo", "Informativo"],
  ["falso_positivo", "Falso positivo"],
];

/**
 * Convert a free-form name into the canonical TUIC code shape used by
 * the seed and the existing global taxonomies (UPPER-CASE, ASCII-only,
 * hyphen-separated, max 50 chars).
 *
 * Examples:
 *   "Ransomware LockBit"      -> "RANSOMWARE-LOCKBIT"
 *   "Ingeniería Social"       -> "INGENIERIA-SOCIAL"
 *   "Phishing - SMS  / Vish." -> "PHISHING-SMS-VISH"
 */
function slugifyTuic(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // strip diacritics
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

interface TaxonomyEditModalProps {
  isOpen: boolean;
  /** When set, modal is in edit mode; otherwise create mode. */
  existing?: SecurityTaxonomy | null;
  /** Parent taxonomy options (for parent_id picker — typically the tree flattened). */
  parentOptions?: Array<{ id: string; tuic_code: string; name: string }>;
  onClose: () => void;
  onSaved?: (taxonomy: SecurityTaxonomy) => void;
}

type FormState = {
  tenant_id: string | null;
  tuic_code: string;
  name: string;
  description: string;
  parent_id: string;
  attack_type: string;
  attack_subtype: string;
  internal_impact_context: string;
  external_impact_context: string;
  managed_by_team_id: string;
  default_case_type: TaxonomyDefaultCaseType;
  requires_ticket: boolean;
  triage_mode: TriageMode;
  delegated_workflow_id: string;
  triage_timeout_seconds: number;
  tlp_default: TLP;
  prioritization_formula_id: string;
  mitre_techniques: string[];
};

const EMPTY_STATE: FormState = {
  tenant_id: null,
  tuic_code: "",
  name: "",
  description: "",
  parent_id: "",
  attack_type: "",
  attack_subtype: "",
  internal_impact_context: "",
  external_impact_context: "",
  managed_by_team_id: "",
  default_case_type: "event",
  requires_ticket: false,
  triage_mode: "auto",
  delegated_workflow_id: "",
  triage_timeout_seconds: 300,
  tlp_default: "amber",
  prioritization_formula_id: "",
  mitre_techniques: [],
};

export function TaxonomyEditModal({
  isOpen,
  existing,
  parentOptions = [],
  onClose,
  onSaved,
}: TaxonomyEditModalProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [form, setForm] = useState<FormState>(EMPTY_STATE);
  // Tracks whether the user manually edited the TUIC field. Once true,
  // typing in `name` no longer auto-overrides the code (avoids stomping
  // a deliberate override every keystroke).
  const [tuicTouched, setTuicTouched] = useState(false);

  const createMutation = useCreateTaxonomy();
  const updateMutation = useUpdateTaxonomy();
  const mutation = existing ? updateMutation : createMutation;

  // Hydrate state when opening / switching record
  useEffect(() => {
    if (!isOpen) return;
    if (existing) {
      setForm({
        tenant_id: existing.tenant_id,
        tuic_code: existing.tuic_code,
        name: existing.name,
        description: existing.description ?? "",
        parent_id: existing.parent_id ?? "",
        attack_type: existing.attack_type ?? "",
        attack_subtype: existing.attack_subtype ?? "",
        internal_impact_context: existing.internal_impact_context ?? "",
        external_impact_context: existing.external_impact_context ?? "",
        managed_by_team_id: existing.managed_by_team_id ?? "",
        default_case_type: existing.default_case_type,
        requires_ticket: existing.requires_ticket,
        triage_mode: existing.triage_mode,
        delegated_workflow_id: existing.delegated_workflow_id ?? "",
        triage_timeout_seconds: existing.triage_timeout_seconds,
        tlp_default: existing.tlp_default,
        prioritization_formula_id: existing.prioritization_formula_id ?? "",
        mitre_techniques: existing.mitre_techniques ?? [],
      });
    } else {
      setForm(EMPTY_STATE);
    }
    setStep(1);
    // Edit mode: the existing tuic_code is canonical, treat it as
    // "user-provided" so we never touch it. Create mode: start in
    // auto-sync mode.
    setTuicTouched(!!existing);
  }, [isOpen, existing]);

  const validation = useMemo(() => validateForm(form, !existing), [form, existing]);

  if (!isOpen) return null;

  async function handleSave() {
    const techniques = form.mitre_techniques;

    if (existing) {
      const payload: UpdateTaxonomyPayload = {
        name: form.name,
        description: form.description || null,
        parent_id: form.parent_id || null,
        attack_type: form.attack_type || null,
        attack_subtype: form.attack_subtype || null,
        internal_impact_context: form.internal_impact_context || null,
        external_impact_context: form.external_impact_context || null,
        managed_by_team_id: form.managed_by_team_id || null,
        default_case_type: form.default_case_type,
        requires_ticket: form.requires_ticket,
        triage_mode: form.triage_mode,
        delegated_workflow_id: form.delegated_workflow_id || null,
        triage_timeout_seconds: form.triage_timeout_seconds,
        tlp_default: form.tlp_default,
        prioritization_formula_id: form.prioritization_formula_id || null,
        mitre_techniques: techniques,
      };
      const updated = await updateMutation.mutateAsync({ id: existing.id, payload });
      onSaved?.(updated);
    } else {
      const payload: CreateTaxonomyPayload = {
        tenant_id: form.tenant_id,
        tuic_code: form.tuic_code,
        name: form.name,
        description: form.description || null,
        parent_id: form.parent_id || null,
        attack_type: form.attack_type || null,
        attack_subtype: form.attack_subtype || null,
        internal_impact_context: form.internal_impact_context || null,
        external_impact_context: form.external_impact_context || null,
        managed_by_team_id: form.managed_by_team_id || null,
        default_case_type: form.default_case_type,
        requires_ticket: form.requires_ticket,
        triage_mode: form.triage_mode,
        delegated_workflow_id: form.delegated_workflow_id || null,
        triage_timeout_seconds: form.triage_timeout_seconds,
        tlp_default: form.tlp_default,
        prioritization_formula_id: form.prioritization_formula_id || null,
        mitre_techniques: techniques,
      };
      const created = await createMutation.mutateAsync(payload);
      onSaved?.(created);
    }
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-taxonomy-title"
    >
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-lg bg-background shadow-xl">
        <header className="flex items-start justify-between border-b p-4">
          <div>
            <h2 id="edit-taxonomy-title" className="text-lg font-semibold">
              {existing ? "Editar taxonomía" : "Nueva taxonomía"}
            </h2>
            <p className="text-xs text-muted-foreground">
              Paso {step} de 3 — {STEP_LABELS[step]}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        <Stepper currentStep={step} />

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {step === 1 ? (
            <Step1Identity
              form={form} setForm={setForm} editing={!!existing}
              parentOptions={parentOptions}
              tuicTouched={tuicTouched} setTuicTouched={setTuicTouched}
            />
          ) : step === 2 ? (
            <Step2Classification form={form} setForm={setForm} />
          ) : (
            <Step3Operation form={form} setForm={setForm} />
          )}

          {validation.errors.length > 0 ? (
            <ul className="rounded border border-red-300 bg-red-50 p-2 text-xs text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
              {validation.errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          ) : null}

          {mutation.isError ? (
            <p className="text-xs text-red-600">
              {(mutation.error as Error).message}
            </p>
          ) : null}
        </div>

        <footer className="flex items-center justify-between border-t p-3">
          <button
            type="button"
            onClick={() => setStep((s) => (s > 1 ? ((s - 1) as 1 | 2 | 3) : s))}
            disabled={step === 1}
            className="rounded border px-3 py-1 text-sm hover:bg-muted disabled:opacity-50"
          >
            Atrás
          </button>
          {step < 3 ? (
            <button
              type="button"
              onClick={() => setStep((s) => (s + 1) as 1 | 2 | 3)}
              disabled={!validation.canAdvance[step]}
              className={cn(
                "rounded bg-blue-600 px-3 py-1 text-sm font-medium text-white",
                "hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50",
              )}
            >
              Siguiente
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSave}
              disabled={
                validation.errors.length > 0 || mutation.isPending
              }
              className={cn(
                "rounded bg-blue-600 px-3 py-1 text-sm font-medium text-white",
                "hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50",
              )}
            >
              {mutation.isPending
                ? "Guardando..."
                : existing
                  ? "Guardar cambios"
                  : "Crear taxonomía"}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}

// ── Steps ───────────────────────────────────────────────────────────────

const STEP_LABELS: Record<1 | 2 | 3, string> = {
  1: "Identidad",
  2: "Clasificación",
  3: "Operación",
};

function Stepper({ currentStep }: { currentStep: 1 | 2 | 3 }) {
  return (
    <ol className="flex border-b">
      {[1, 2, 3].map((n) => (
        <li
          key={n}
          className={cn(
            "flex flex-1 items-center justify-center gap-1 py-2 text-xs",
            n === currentStep
              ? "border-b-2 border-blue-600 font-semibold text-blue-700 dark:text-blue-400"
              : "text-muted-foreground",
          )}
        >
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full border text-[10px]">
            {n}
          </span>
          {STEP_LABELS[n as 1 | 2 | 3]}
        </li>
      ))}
    </ol>
  );
}

interface StepProps {
  form: FormState;
  setForm: React.Dispatch<React.SetStateAction<FormState>>;
}

function Step1Identity({
  form, setForm, editing, parentOptions,
  tuicTouched, setTuicTouched,
}: StepProps & {
  editing: boolean;
  parentOptions: Array<{ id: string; tuic_code: string; name: string }>;
  tuicTouched: boolean;
  setTuicTouched: (v: boolean) => void;
}) {
  return (
    <>
      <Field label="Nombre" required>
        <input
          type="text"
          value={form.name}
          onChange={(e) => {
            const name = e.target.value;
            setForm((f) => ({
              ...f,
              name,
              // Mirror name -> tuic_code while the user hasn't typed
              // anything in the TUIC field manually.
              tuic_code:
                !editing && !tuicTouched ? slugifyTuic(name) : f.tuic_code,
            }));
          }}
          className="w-full rounded border bg-background p-1 text-sm"
        />
      </Field>
      <Field
        label="TUIC Code"
        required
        hint={
          editing
            ? "El código es inmutable después de crear."
            : tuicTouched
              ? "Edición manual — ya no se sincroniza con el nombre."
              : "Generado automáticamente desde el nombre. Editalo para personalizar."
        }
      >
        <input
          type="text"
          value={form.tuic_code}
          disabled={editing}
          onChange={(e) => {
            setTuicTouched(true);
            setForm((f) => ({ ...f, tuic_code: e.target.value.toUpperCase() }));
          }}
          className="w-full rounded border bg-background p-1 text-sm font-mono"
          placeholder="RANSOM-LOCKBIT"
        />
      </Field>
      <Field label="Descripción">
        <textarea
          value={form.description}
          onChange={(e) =>
            setForm((f) => ({ ...f, description: e.target.value }))
          }
          className="w-full rounded border bg-background p-1 text-sm"
          rows={2}
        />
      </Field>
      <Field
        label="Padre (parent_id)"
        hint="Para jerarquía. Opcional. Selecciona una taxonomía del mismo tenant o global."
      >
        <select
          value={form.parent_id}
          onChange={(e) => setForm((f) => ({ ...f, parent_id: e.target.value }))}
          className="w-full rounded border bg-background p-1 text-sm"
        >
          <option value="">— Sin padre (root) —</option>
          {parentOptions.map((p) => (
            <option key={p.id} value={p.id}>
              {p.tuic_code} — {p.name}
            </option>
          ))}
        </select>
      </Field>
    </>
  );
}

function Step2Classification({ form, setForm }: StepProps) {
  return (
    <>
      <Field label="Tipo de ataque">
        <input
          type="text"
          value={form.attack_type}
          onChange={(e) =>
            setForm((f) => ({ ...f, attack_type: e.target.value }))
          }
          className="w-full rounded border bg-background p-1 text-sm"
        />
      </Field>
      <Field label="Subtipo de ataque">
        <input
          type="text"
          value={form.attack_subtype}
          onChange={(e) =>
            setForm((f) => ({ ...f, attack_subtype: e.target.value }))
          }
          className="w-full rounded border bg-background p-1 text-sm"
        />
      </Field>
      <Field label="Contexto de impacto interno">
        <select
          value={form.internal_impact_context}
          onChange={(e) =>
            setForm((f) => ({ ...f, internal_impact_context: e.target.value }))
          }
          className="w-full rounded border bg-background p-1 text-sm"
        >
          <option value="">— sin asignar —</option>
          {IMPACT_LEVELS.map(([slug, label]) => (
            <option key={slug} value={slug}>
              {label}
            </option>
          ))}
          {/* Legacy free-text values: surface them as a read-only option so
              existing rows don't silently lose their value when re-saved. */}
          {form.internal_impact_context &&
            !IMPACT_LEVELS.some(([s]) => s === form.internal_impact_context) && (
              <option value={form.internal_impact_context}>
                (legacy) {form.internal_impact_context}
              </option>
            )}
        </select>
      </Field>
      <Field label="Contexto de impacto externo">
        <select
          value={form.external_impact_context}
          onChange={(e) =>
            setForm((f) => ({ ...f, external_impact_context: e.target.value }))
          }
          className="w-full rounded border bg-background p-1 text-sm"
        >
          <option value="">— sin asignar —</option>
          {IMPACT_LEVELS.map(([slug, label]) => (
            <option key={slug} value={slug}>
              {label}
            </option>
          ))}
          {form.external_impact_context &&
            !IMPACT_LEVELS.some(([s]) => s === form.external_impact_context) && (
              <option value={form.external_impact_context}>
                (legacy) {form.external_impact_context}
              </option>
            )}
        </select>
      </Field>
      <Field
        label="MITRE ATT&CK Techniques"
        hint="Selecciona desde el catálogo MITRE — no se aceptan IDs libres"
      >
        <MitreTechniqueChips
          selected={form.mitre_techniques}
          onChange={(ids) =>
            setForm((f) => ({ ...f, mitre_techniques: ids }))
          }
        />
      </Field>
    </>
  );
}

function Step3Operation({ form, setForm }: StepProps) {
  // Active workflows for the delegated_workflow_id dropdown. React Query
  // dedupes if parent components also subscribe to this key.
  const { data: catalogWorkflows } = useN8nWorkflows({ only_active: true });
  return (
    <>
      <Field label="Tipo de caso default" required>
        <div className="flex gap-3 text-sm">
          {(["event", "incident"] as const).map((opt) => (
            <label key={opt} className="flex items-center gap-1">
              <input
                type="radio"
                name="default_case_type"
                value={opt}
                checked={form.default_case_type === opt}
                onChange={() =>
                  setForm((f) => ({ ...f, default_case_type: opt }))
                }
              />
              {opt}
            </label>
          ))}
        </div>
      </Field>
      <Field label="Requiere ticket">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.requires_ticket}
            onChange={(e) =>
              setForm((f) => ({ ...f, requires_ticket: e.target.checked }))
            }
          />
          Crear ticket completo (vs. solo evento/log)
        </label>
      </Field>
      <Field label="Modo de triage" required>
        <select
          value={form.triage_mode}
          onChange={(e) =>
            setForm((f) => ({ ...f, triage_mode: e.target.value as TriageMode }))
          }
          className="w-full rounded border bg-background p-1 text-sm"
        >
          <option value="auto">auto</option>
          <option value="delegate_to_n8n">delegate_to_n8n</option>
        </select>
      </Field>
      {form.triage_mode === "delegate_to_n8n" ? (
        <Field
          label="Workflow delegado"
          required
          hint="Selecciona del catálogo registrado en /settings/integrations → Workflows n8n"
        >
          <select
            value={form.delegated_workflow_id}
            onChange={(e) =>
              setForm((f) => ({
                ...f, delegated_workflow_id: e.target.value,
              }))
            }
            className="w-full rounded border bg-background p-1 text-sm"
          >
            <option value="">— Selecciona un workflow —</option>
            {catalogWorkflows?.map((wf) => (
              <option key={wf.id} value={wf.id}>
                {wf.tenant_id === null ? "[global] " : ""}
                {wf.name}
                {wf.requires_approval ? " · requiere aprobación" : ""}
              </option>
            ))}
          </select>
          {catalogWorkflows && catalogWorkflows.length === 0 ? (
            <p className="mt-1 text-xs text-amber-600">
              Sin workflows en el catálogo. Regístralos primero en{" "}
              <span className="font-mono">/settings/integrations</span> &gt;
              Workflows n8n.
            </p>
          ) : null}
        </Field>
      ) : null}
      <Field label="Timeout triage (segundos)">
        <input
          type="number"
          min={1}
          value={form.triage_timeout_seconds}
          onChange={(e) =>
            setForm((f) => ({
              ...f,
              triage_timeout_seconds: Number(e.target.value) || 0,
            }))
          }
          className="w-full rounded border bg-background p-1 text-sm"
        />
      </Field>
      <Field label="TLP default" required>
        <select
          value={form.tlp_default}
          onChange={(e) =>
            setForm((f) => ({ ...f, tlp_default: e.target.value as TLP }))
          }
          className="w-full rounded border bg-background p-1 text-sm"
        >
          {(["white", "green", "amber", "red"] as const).map((t) => (
            <option key={t} value={t}>
              {t.toUpperCase()}
            </option>
          ))}
        </select>
      </Field>
    </>
  );
}

function Field({
  label, required, hint, children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-medium">
        {label}
        {required ? <span className="text-red-600"> *</span> : null}
      </label>
      {hint ? (
        <p className="text-[10px] text-muted-foreground mb-1">{hint}</p>
      ) : null}
      <div className="mt-0.5">{children}</div>
    </div>
  );
}

// ── Validation ──────────────────────────────────────────────────────────

function validateForm(form: FormState, isCreate: boolean): {
  errors: string[];
  canAdvance: Record<1 | 2 | 3, boolean>;
} {
  const errors: string[] = [];

  // Step 1
  const step1Ok = Boolean(
    (isCreate ? form.tuic_code.trim() : true) && form.name.trim(),
  );
  if (isCreate && !form.tuic_code.trim()) {
    errors.push("TUIC code es requerido");
  }
  if (!form.name.trim()) {
    errors.push("Nombre es requerido");
  }

  // Step 3 — delegate_to_n8n requires workflow_id
  if (
    form.triage_mode === "delegate_to_n8n" &&
    !form.delegated_workflow_id.trim()
  ) {
    errors.push(
      "delegated_workflow_id es requerido cuando triage_mode = delegate_to_n8n",
    );
  }

  if (form.triage_timeout_seconds <= 0) {
    errors.push("triage_timeout_seconds debe ser > 0");
  }

  return {
    errors,
    canAdvance: {
      1: step1Ok,
      2: step1Ok,
      3: step1Ok,
    },
  };
}

// ─── MITRE technique chips + picker trigger ───────────────────
function MitreTechniqueChips({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const { data: byId = {} } = useMitreTechniquesByIds(selected);

  function removeId(id: string) {
    onChange(selected.filter((x) => x !== id));
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {selected.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Sin técnicas asociadas.
        </p>
      )}
      {selected.map((id) => {
        const t = byId[id];
        return (
          <span
            key={id}
            className="inline-flex items-center gap-1 rounded-md border border-border bg-muted/40 px-1.5 py-0.5 text-xs"
            title={t?.name ?? id}
          >
            <code className="font-mono text-[10px] text-muted-foreground">
              {id}
            </code>
            {t?.name && (
              <span className="truncate max-w-[160px]">{t.name}</span>
            )}
            <button
              type="button"
              onClick={() => removeId(id)}
              className="rounded p-0.5 hover:bg-destructive/10 hover:text-destructive"
              aria-label={`Quitar ${id}`}
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        );
      })}
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => setPickerOpen(true)}
      >
        <Plus className="h-3.5 w-3.5 mr-1" />
        Agregar
      </Button>
      <MitreTechniquePickerModal
        open={pickerOpen}
        initialSelected={selected}
        onClose={() => setPickerOpen(false)}
        onSave={(ids) => {
          onChange(ids);
          setPickerOpen(false);
        }}
      />
    </div>
  );
}
