"use client";

import { X } from "lucide-react";
import { useEffect, useState } from "react";

import {
  useCreateN8nWorkflow,
  useUpdateN8nWorkflow,
} from "@/hooks/useN8nWorkflows";
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
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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
      setErrorMsg(null);
    }
  }, [isOpen, initial, prefill]);

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
            <label className="text-xs text-muted-foreground">URL del workflow (webhook n8n)</label>
            <input
              className={`${inputCls} font-mono text-xs`}
              value={workflowUrl}
              onChange={(e) => setWorkflowUrl(e.target.value)}
              placeholder="https://n8n.example.com/webhook/..."
            />
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
