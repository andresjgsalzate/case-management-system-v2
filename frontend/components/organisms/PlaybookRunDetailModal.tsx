"use client";

import { ChevronRight, X } from "lucide-react";
import { useState } from "react";

import {
  usePlaybookRunCallbacks,
  usePlaybookRunDetail,
} from "@/hooks/usePlaybookRuns";
import type { PlaybookRunCallback } from "@/lib/types";

interface Props {
  runId: string | null;
  onClose: () => void;
}

export function PlaybookRunDetailModal({ runId, onClose }: Props) {
  const { data: run, isLoading: runLoading } = usePlaybookRunDetail(runId);
  const { data: callbacks, isLoading: cbsLoading } = usePlaybookRunCallbacks(runId);

  if (!runId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded-lg bg-card shadow-xl">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-base font-semibold">Detalle del playbook run</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="space-y-4 p-4 text-sm">
          {runLoading ? (
            <p>Cargando run…</p>
          ) : !run ? (
            <p>No encontrado.</p>
          ) : (
            <section>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                <dt className="font-medium text-muted-foreground">ID</dt>
                <dd className="font-mono">{run.id}</dd>
                <dt className="font-medium text-muted-foreground">Workflow</dt>
                <dd className="break-all font-mono">{run.workflow_url}</dd>
                <dt className="font-medium text-muted-foreground">Estado</dt>
                <dd>{run.status}</dd>
                <dt className="font-medium text-muted-foreground">Disparado por</dt>
                <dd>{run.triggered_by}</dd>
                <dt className="font-medium text-muted-foreground">Disparado en</dt>
                <dd>{new Date(run.triggered_at).toLocaleString()}</dd>
                <dt className="font-medium text-muted-foreground">Completado</dt>
                <dd>
                  {run.completed_at
                    ? new Date(run.completed_at).toLocaleString()
                    : "—"}
                </dd>
                <dt className="font-medium text-muted-foreground">n8n exec id</dt>
                <dd className="font-mono">{run.n8n_execution_id ?? "—"}</dd>
                <dt className="font-medium text-muted-foreground">Decisión final</dt>
                <dd>{run.final_decision ?? "—"}</dd>
              </dl>

              {run.error ? (
                <pre className="mt-3 overflow-auto rounded bg-red-50 p-2 text-xs text-red-900">
                  {run.error}
                </pre>
              ) : null}
            </section>
          )}

          <section>
            <h3 className="mb-2 text-sm font-semibold">
              Callbacks ({callbacks?.length ?? 0})
            </h3>
            {cbsLoading ? (
              <p className="text-xs text-muted-foreground">Cargando callbacks…</p>
            ) : !callbacks || callbacks.length === 0 ? (
              <p className="rounded border border-dashed p-3 text-xs text-muted-foreground">
                Aún no hay callbacks. n8n no ha respondido todavía.
              </p>
            ) : (
              <ol className="space-y-2">
                {callbacks.map((cb) => (
                  <CallbackEntry key={cb.id} callback={cb} />
                ))}
              </ol>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function CallbackEntry({ callback }: { callback: PlaybookRunCallback }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li className="rounded border">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted/30"
      >
        <ChevronRight
          className={`h-3 w-3 transition-transform ${expanded ? "rotate-90" : ""}`}
        />
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
            callback.success
              ? "bg-green-100 text-green-800"
              : "bg-red-100 text-red-800"
          }`}
        >
          {callback.success ? "OK" : "FAIL"}
        </span>
        <span className="font-mono">{callback.action}</span>
        <span className="ml-auto text-muted-foreground">
          {new Date(callback.received_at).toLocaleString()}
        </span>
      </button>
      {expanded ? (
        <div className="space-y-2 border-t bg-muted/20 p-3 text-xs">
          {callback.error ? (
            <div>
              <p className="font-semibold text-red-700">Error</p>
              <pre className="overflow-auto rounded bg-red-50 p-2 text-red-900">
                {callback.error}
              </pre>
            </div>
          ) : null}
          <div>
            <p className="font-semibold">Payload de n8n</p>
            <pre className="overflow-auto rounded bg-card p-2">
              {JSON.stringify(callback.payload, null, 2)}
            </pre>
          </div>
          {callback.response_payload ? (
            <div>
              <p className="font-semibold">Respuesta de CMS</p>
              <pre className="overflow-auto rounded bg-card p-2">
                {JSON.stringify(callback.response_payload, null, 2)}
              </pre>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
