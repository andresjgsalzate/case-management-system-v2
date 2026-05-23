"use client";

import { AlertCircle, CheckCircle2, X } from "lucide-react";
import { useEffect, useState } from "react";

import {
  useCreateN8nWorkflow,
  useUpdateN8nWorkflow,
} from "@/hooks/useN8nWorkflows";
import { useN8nWorkflowWebhooks } from "@/hooks/useN8nWorkflowWebhooks";
import type {
  CreateN8nWorkflowPayload,
  N8nWorkflow,
} from "@/lib/types";

interface Props {
  isOpen: boolean;
  initial?: N8nWorkflow | null;
  /**
   * Pre-fill values for *create* mode (no `initial`). Used when
   * registering an orphan from the n8n inventory page: the orphan's
   * n8n name + id are passed in so the operator only has to fill the
   * webhook URL + curation flags. n8n_workflow_id is locked in this
   * path so the new catalog row immediately links back to its n8n
   * counterpart and the inventory flips it to "registered".
   */
  prefill?: {
    name?: string;
    n8n_workflow_id?: string;
  } | null;
  onClose: () => void;
}

const inputCls =
  "px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary w-full";

export function N8nWorkflowFormModal({
  isOpen, initial, prefill, onClose,
}: Props) {
  const create = useCreateN8nWorkflow();
  const update = useUpdateN8nWorkflow();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [workflowUrl, setWorkflowUrl] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [requiresApproval, setRequiresApproval] = useState(false);
  const [n8nWorkflowId, setN8nWorkflowId] = useState("");
  // Tracks whether the URL field has been touched by the user. When
  // auto-discovery returns a webhook for an orphan registration, we
  // only pre-fill if the user hasn't typed anything yet.
  const [urlTouched, setUrlTouched] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Discover webhook entry points for the linked n8n workflow. Only
  // fires in create mode when we have an n8n_workflow_id (i.e. the
  // operator is registering an orphan from the inventory).
  const discoveryEnabled =
    !initial && !!n8nWorkflowId && !!prefill?.n8n_workflow_id;
  const { data: webhooks, isLoading: webhooksLoading } =
    useN8nWorkflowWebhooks(discoveryEnabled ? n8nWorkflowId : null);

  // Reset form when initial / prefill changes or modal opens. `initial`
  // wins (edit mode); otherwise `prefill` seeds the create form.
  useEffect(() => {
    if (isOpen) {
      setName(initial?.name ?? prefill?.name ?? "");
      setDescription(initial?.description ?? "");
      setWorkflowUrl(initial?.workflow_url ?? "");
      setIsActive(initial?.is_active ?? true);
      setRequiresApproval(initial?.requires_approval ?? false);
      // Locked when prefilled from an orphan (preserves the link).
      setN8nWorkflowId(prefill?.n8n_workflow_id ?? "");
      setUrlTouched(!!initial?.workflow_url);
      setErrorMsg(null);
    }
  }, [isOpen, initial, prefill]);

  // Auto-fill URL the moment discovery returns exactly one webhook
  // (and the user hasn't typed anything yet). With multiple matches
  // we render a dropdown below so the operator can pick.
  useEffect(() => {
    if (urlTouched || !webhooks || webhooks.length !== 1) return;
    setWorkflowUrl(webhooks[0].url);
  }, [webhooks, urlTouched]);

  if (!isOpen) return null;

  const editing = Boolean(initial);
  const pending = create.isPending || update.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg(null);
    if (!name.trim()) {
      setErrorMsg("El nombre es requerido");
      return;
    }
    if (!workflowUrl.trim()) {
      setErrorMsg("La URL del workflow es requerida");
      return;
    }
    try {
      const linkId = n8nWorkflowId.trim() || null;
      if (editing && initial) {
        await update.mutateAsync({
          id: initial.id,
          body: {
            name: name.trim(),
            description: description.trim() || null,
            workflow_url: workflowUrl.trim(),
            is_active: isActive,
            requires_approval: requiresApproval,
            n8n_workflow_id: linkId,
          },
        });
      } else {
        const payload: CreateN8nWorkflowPayload = {
          name: name.trim(),
          description: description.trim() || null,
          workflow_url: workflowUrl.trim(),
          is_active: isActive,
          requires_approval: requiresApproval,
          n8n_workflow_id: linkId,
        };
        await create.mutateAsync(payload);
      }
      onClose();
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
      setErrorMsg(
        detail ??
          (err instanceof Error ? err.message : "Error al guardar workflow"),
      );
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-xl overflow-auto rounded-lg bg-card shadow-xl">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-base font-semibold">
            {editing ? "Editar workflow" : "Nuevo workflow n8n"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <form onSubmit={handleSubmit} className="space-y-3 p-4">
          {errorMsg && (
            <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
              {errorMsg}
            </p>
          )}

          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Nombre</label>
            <input
              className={inputCls}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ej: Bloquear IP maliciosa"
              autoFocus
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Descripción</label>
            <input
              className={inputCls}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Qué hace este workflow"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">
              URL del workflow (webhook n8n)
            </label>
            <input
              className={`${inputCls} font-mono text-xs`}
              value={workflowUrl}
              onChange={(e) => {
                setUrlTouched(true);
                setWorkflowUrl(e.target.value);
              }}
              placeholder="https://cms.local/webhook/..."
            />
            {discoveryEnabled && (
              <DiscoveryHint
                loading={webhooksLoading}
                webhooks={webhooks}
                currentUrl={workflowUrl}
                onPick={(url) => {
                  setUrlTouched(true);
                  setWorkflowUrl(url);
                }}
              />
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">
              ID interno n8n (opcional, enlaza con el inventario)
            </label>
            <input
              className={`${inputCls} font-mono text-xs`}
              value={n8nWorkflowId}
              onChange={(e) => setN8nWorkflowId(e.target.value)}
              placeholder="F7v469lghiBA7FcX"
              // Locked when registering an orphan: the id comes from
              // the inventory and changing it would break the link.
              disabled={!!prefill?.n8n_workflow_id}
            />
            {prefill?.n8n_workflow_id ? (
              <p className="text-[11px] text-muted-foreground">
                Heredado del workflow huérfano · no editable
              </p>
            ) : null}
          </div>

          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
              />
              Activo
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={requiresApproval}
                onChange={(e) => setRequiresApproval(e.target.checked)}
              />
              Requiere aprobación
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={pending}
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {pending ? "Guardando…" : editing ? "Guardar" : "Crear"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Discovery hint: shows the auto-detect status under the URL input ─

function DiscoveryHint({
  loading, webhooks, currentUrl, onPick,
}: {
  loading: boolean;
  webhooks: { path: string; url: string; http_method: string; node_name: string }[] | undefined;
  currentUrl: string;
  onPick: (url: string) => void;
}) {
  if (loading) {
    return (
      <p className="text-[11px] text-muted-foreground mt-1">
        Buscando webhooks en n8n…
      </p>
    );
  }
  if (!webhooks) return null;

  if (webhooks.length === 0) {
    return (
      <div className="mt-1 flex items-start gap-1 text-[11px] text-amber-600">
        <AlertCircle className="h-3 w-3 mt-0.5 shrink-0" />
        <span>
          Este workflow no expone webhooks. Si igual querés registrarlo,
          tipeá una URL placeholder (no podrá ser disparado por HTTP).
        </span>
      </div>
    );
  }

  if (webhooks.length === 1) {
    return (
      <div className="mt-1 flex items-start gap-1 text-[11px] text-emerald-600">
        <CheckCircle2 className="h-3 w-3 mt-0.5 shrink-0" />
        <span>
          Webhook auto-detectado desde n8n ({webhooks[0].http_method} ·{" "}
          nodo &quot;{webhooks[0].node_name}&quot;).
        </span>
      </div>
    );
  }

  return (
    <div className="mt-1 space-y-1">
      <p className="text-[11px] text-muted-foreground">
        Este workflow tiene {webhooks.length} webhooks. Elegí cuál usar:
      </p>
      <select
        value={currentUrl}
        onChange={(e) => onPick(e.target.value)}
        className={`${inputCls} text-xs`}
      >
        <option value="">— elegir webhook —</option>
        {webhooks.map((w) => (
          <option key={w.path} value={w.url}>
            {w.http_method} · {w.node_name} · /{w.path}
          </option>
        ))}
      </select>
    </div>
  );
}
