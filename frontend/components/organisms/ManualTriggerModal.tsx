"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { useManualTriggerWorkflow } from "@/hooks/usePlaybookRuns";

interface Props {
  isOpen: boolean;
  caseId: string;
  onClose: () => void;
  onTriggered?: (runId: string) => void;
}

export function ManualTriggerModal({ isOpen, caseId, onClose, onTriggered }: Props) {
  const trigger = useManualTriggerWorkflow();
  const [workflowUrl, setWorkflowUrl] = useState("");
  const [extraContextJson, setExtraContextJson] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  function close() {
    setWorkflowUrl("");
    setExtraContextJson("");
    setErrorMsg(null);
    onClose();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg(null);

    if (!workflowUrl.trim()) {
      setErrorMsg("workflow_url es requerido");
      return;
    }

    let extra: Record<string, unknown> | undefined;
    if (extraContextJson.trim()) {
      try {
        const parsed = JSON.parse(extraContextJson);
        if (typeof parsed !== "object" || Array.isArray(parsed) || parsed === null) {
          throw new Error("extra_context debe ser un objeto JSON");
        }
        extra = parsed as Record<string, unknown>;
      } catch (err) {
        setErrorMsg(
          err instanceof Error ? `JSON inválido: ${err.message}` : "JSON inválido",
        );
        return;
      }
    }

    try {
      const run = await trigger.mutateAsync({
        caseId,
        payload: {
          workflow_url: workflowUrl.trim(),
          extra_context: extra ?? null,
        },
      });
      onTriggered?.(run.id);
      close();
    } catch (err) {
      setErrorMsg(
        err instanceof Error ? err.message : "Error al disparar el workflow",
      );
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-xl rounded-lg bg-card shadow-xl">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-base font-semibold">Disparar workflow n8n</h2>
          <button
            type="button"
            onClick={close}
            className="rounded p-1 hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <form onSubmit={handleSubmit} className="space-y-4 p-4">
          <label className="block text-sm">
            <span className="mb-1 block font-medium">workflow_url *</span>
            <input
              type="url"
              value={workflowUrl}
              onChange={(e) => setWorkflowUrl(e.target.value)}
              placeholder="https://n8n.local/webhook/abc-123"
              className="w-full rounded border px-2 py-1 text-sm font-mono"
            />
            <span className="mt-1 block text-xs text-muted-foreground">
              URL completa del webhook n8n a llamar.
            </span>
          </label>

          <label className="block text-sm">
            <span className="mb-1 block font-medium">extra_context (JSON, opcional)</span>
            <textarea
              value={extraContextJson}
              onChange={(e) => setExtraContextJson(e.target.value)}
              rows={5}
              placeholder='{"reason": "manual run", "hint": "..."}'
              className="w-full rounded border px-2 py-1 text-sm font-mono"
            />
          </label>

          {errorMsg ? (
            <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
              {errorMsg}
            </p>
          ) : null}

          <footer className="flex justify-end gap-2 border-t pt-3">
            <button
              type="button"
              onClick={close}
              className="rounded border px-3 py-1.5 text-sm hover:bg-muted"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={trigger.isPending}
              className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {trigger.isPending ? "Disparando…" : "Disparar"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
