"use client";

import {
  useForensicHuntDetail,
  useForensicHuntResults,
} from "@/hooks/useForensicHunts";

import { ChainOfCustodyPanel } from "./ChainOfCustodyPanel";

interface Props {
  huntId: string | null;
  onClose: () => void;
}

export function HuntDetailDrawer({ huntId, onClose }: Props) {
  const huntQuery = useForensicHuntDetail(huntId);
  const resultsQuery = useForensicHuntResults(huntId);

  if (!huntId) return null;

  const hunt = huntQuery.data;
  const results = resultsQuery.data ?? [];

  return (
    <aside
      role="complementary"
      aria-labelledby="hunt-drawer-title"
      className="fixed inset-y-0 right-0 w-[600px] bg-white shadow-2xl border-l z-50 overflow-y-auto"
    >
      <div className="p-4 border-b flex justify-between items-center sticky top-0 bg-white">
        <h2 id="hunt-drawer-title" className="text-lg font-semibold">
          Detalle del hunt
        </h2>
        <button
          type="button"
          aria-label="Cerrar"
          onClick={onClose}
          className="text-2xl leading-none"
        >
          ×
        </button>
      </div>

      <div className="p-4 space-y-4">
        {huntQuery.isLoading && (
          <div className="text-sm text-gray-500">Cargando hunt...</div>
        )}

        {hunt && (
          <>
            <div>
              <div className="font-mono text-sm font-medium">
                {hunt.artifact_name}
              </div>
              <div className="text-sm text-gray-600">
                {hunt.target_label ?? "—"}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Estado: <span className="font-medium">{hunt.status}</span>
              </div>
              {hunt.error && (
                <div
                  role="alert"
                  className="text-xs text-red-600 mt-2 break-words"
                >
                  {hunt.error}
                </div>
              )}
            </div>

            <ChainOfCustodyPanel hunt={hunt} />

            {hunt.result_summary && (
              <section aria-labelledby="hunt-summary-title">
                <h3 id="hunt-summary-title" className="font-semibold mb-2">
                  Resumen
                </h3>
                <div className="text-sm space-y-1">
                  <div>Total filas: {hunt.result_summary.total_rows}</div>
                  <div>Hosts: {hunt.result_summary.client_count}</div>
                </div>
                {hunt.result_summary.sample_rows.length > 0 && (
                  <pre className="text-xs bg-gray-100 p-2 mt-2 overflow-x-auto rounded">
                    {JSON.stringify(
                      hunt.result_summary.sample_rows,
                      null,
                      2,
                    )}
                  </pre>
                )}
              </section>
            )}

            <section aria-labelledby="hunt-results-title">
              <h3 id="hunt-results-title" className="font-semibold mb-2">
                Resultados por host ({results.length})
              </h3>
              {resultsQuery.isLoading && (
                <div className="text-sm text-gray-500">
                  Cargando resultados...
                </div>
              )}
              {!resultsQuery.isLoading && results.length === 0 && (
                <div className="text-sm text-gray-500">
                  Aún sin resultados.
                </div>
              )}
              <ul className="text-sm space-y-1">
                {results.map((r) => (
                  <li key={r.id} className="border rounded p-2">
                    <div className="font-mono">
                      {r.hostname || r.velo_client_id}
                    </div>
                    <div className="text-xs text-gray-600">
                      {r.os ?? "—"} · {r.output_total_rows} filas ·{" "}
                      {r.attachments_count} adjuntos
                    </div>
                    {r.row_hash && (
                      <div className="text-xs font-mono text-gray-500 mt-1 break-all">
                        hash: {r.row_hash}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </div>
    </aside>
  );
}
