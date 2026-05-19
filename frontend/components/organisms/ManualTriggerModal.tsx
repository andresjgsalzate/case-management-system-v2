"use client";

import { X } from "lucide-react";
import { useMemo, useState } from "react";

import { useN8nWorkflows } from "@/hooks/useN8nWorkflows";
import { useManualTriggerWorkflow } from "@/hooks/usePlaybookRuns";

interface Props {
  isOpen: boolean;
  caseId: string;
  onClose: () => void;
  onTriggered?: (runId: string) => void;
}

type Mode = "catalog" | "manual";

export function ManualTriggerModal({ isOpen, caseId, onClose, onTriggered }: Props) {
  const trigger = useManualTriggerWorkflow();
  const { data: catalog, isLoading: catalogLoading } = useN8nWorkflows({
    only_active: true,
  });
  const [mode, setMode] = useState<Mode>("catalog");
  const [selectedId, setSelectedId] = useState<string>("");
  const [workflowUrl, setWorkflowUrl] = useState("");
  const [extraContextJson, setExtraContextJson] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const selectedWorkflow = useMemo(
    () => catalog?.find((w) => w.id === selectedId) ?? null,
    [catalog, selectedId],
  );

  if (!isOpen) return null;

  function close() {
    setMode("catalog");
    setSelectedId("");
    setWorkflowUrl("");
    setExtraContextJson("");
    setErrorMsg(null);
    onClose();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg(null);

    // Resolve the actual URL to send: from catalog selection or manual input.
    let resolvedUrl: string;
    if (mode === "catalog") {
      if (!selectedWorkflow) {
        setErrorMsg("Selecciona un workflow del catálogo");
        return;
      }
      resolvedUrl = selectedWorkflow.workflow_url;
    } else {
      if (!workflowUrl.trim()) {
        setErrorMsg("workflow_url es requerido");
        return;
      }
      resolvedUrl = workflowUrl.trim();
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
          workflow_url: resolvedUrl,
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
          {/* Mode toggle: prefer catalog, fall back to manual URL */}
          <div className="flex gap-1 rounded-md border bg-muted/30 p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setMode("catalog")}
              className={`flex-1 rounded px-2 py-1 transition-colors ${
                mode === "catalog"
                  ? "bg-card font-medium shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Catálogo
            </button>
            <button
              type="button"
              onClick={() => setMode("manual")}
              className={`flex-1 rounded px-2 py-1 transition-colors ${
                mode === "manual"
                  ? "bg-card font-medium shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              URL manual
            </button>
          </div>

          {mode === "catalog" ? (
            <label className="block text-sm">
              <span className="mb-1 block font-medium">Workflow *</span>
              <select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                className="w-full rounded border px-2 py-1.5 text-sm"
                disabled={catalogLoading}
              >
                <option value="">
                  {catalogLoading
                    ? "Cargando catálogo…"
                    : "— Selecciona un workflow —"}
                </option>
                {catalog?.map((wf) => (
                  <option key={wf.id} value={wf.id}>
                    {wf.tenant_id === null ? "[global] " : ""}
                    {wf.name}
                    {wf.requires_approval ? " · requiere aprobación" : ""}
                  </option>
                ))}
              </select>
              {selectedWorkflow?.description && (
                <span className="mt-1 block text-xs text-muted-foreground">
                  {selectedWorkflow.description}
                </span>
              )}
              {!catalogLoading && catalog && catalog.length === 0 && (
                <span className="mt-1 block text-xs text-amber-600">
                  Sin workflows en el catálogo. Regístralos en{" "}
                  <span className="font-mono">/settings/integrations</span> &gt;
                  Workflows n8n.
                </span>
              )}
            </label>
          ) : (
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
          )}

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
