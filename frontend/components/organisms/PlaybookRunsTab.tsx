"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { ManualTriggerModal } from "@/components/organisms/ManualTriggerModal";
import { PlaybookRunDetailModal } from "@/components/organisms/PlaybookRunDetailModal";
import { usePlaybookRuns } from "@/hooks/usePlaybookRuns";
import type { PlaybookRunStatus } from "@/lib/types";

const STATUS_COLOR: Record<PlaybookRunStatus, string> = {
  triggered: "bg-blue-100 text-blue-800",
  running:   "bg-amber-100 text-amber-800",
  completed: "bg-green-100 text-green-800",
  failed:    "bg-red-100 text-red-800",
  timeout:   "bg-orange-100 text-orange-800",
  cancelled: "bg-gray-100 text-gray-700",
};

interface Props {
  caseId: string;
}

export function PlaybookRunsTab({ caseId }: Props) {
  const { data, isLoading, error } = usePlaybookRuns({ case_id: caseId });
  const [triggerOpen, setTriggerOpen] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  return (
    <div className="space-y-3 p-3">
      <header className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">Playbook runs</h3>
          <p className="text-xs text-muted-foreground">
            Ejecuciones de workflows n8n disparadas para este caso.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setTriggerOpen(true)}
          className="inline-flex items-center gap-1 rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-3.5 w-3.5" /> Disparar workflow
        </button>
      </header>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Cargando runs…</p>
      ) : error ? (
        <p className="text-sm text-red-600">Error al cargar runs.</p>
      ) : !data || data.length === 0 ? (
        <p className="rounded border border-dashed bg-muted/20 p-4 text-sm text-muted-foreground">
          Aún no hay ejecuciones para este caso.
        </p>
      ) : (
        <div className="overflow-auto rounded border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Disparado</th>
                <th className="px-3 py-2 font-medium">Por</th>
                <th className="px-3 py-2 font-medium">Workflow</th>
                <th className="px-3 py-2 font-medium">Estado</th>
                <th className="px-3 py-2 font-medium">Callbacks</th>
                <th className="px-3 py-2 font-medium">Decisión</th>
                <th className="px-3 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {data.map((run) => (
                <tr
                  key={run.id}
                  className="border-b last:border-0 hover:bg-muted/30"
                >
                  <td className="px-3 py-2 font-mono text-xs">
                    {new Date(run.triggered_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-xs">{run.triggered_by}</td>
                  <td className="max-w-xs px-3 py-2 font-mono text-xs">
                    <span className="line-clamp-1" title={run.workflow_url}>
                      {run.workflow_id ?? run.workflow_url}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded px-1.5 py-0.5 text-xs font-medium ${STATUS_COLOR[run.status]}`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs">{run.callback_count}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {run.final_decision ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => setSelectedRunId(run.id)}
                      className="rounded border px-2 py-0.5 text-xs hover:bg-muted"
                    >
                      Ver detalle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ManualTriggerModal
        isOpen={triggerOpen}
        caseId={caseId}
        onClose={() => setTriggerOpen(false)}
        onTriggered={(runId) => setSelectedRunId(runId)}
      />

      <PlaybookRunDetailModal
        runId={selectedRunId}
        onClose={() => setSelectedRunId(null)}
      />
    </div>
  );
}
