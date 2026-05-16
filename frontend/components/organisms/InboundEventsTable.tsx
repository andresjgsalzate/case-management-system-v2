"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";

import {
  useInboundEvents,
  useReplayInboundEvent,
} from "@/hooks/useInboundEvents";
import type { InboundEvent, InboundEventStatus } from "@/lib/types";

interface Props {
  onSelect: (event: InboundEvent) => void;
}

const STATUSES: InboundEventStatus[] = [
  "pending", "processing", "processed", "failed", "duplicate",
];

const STATUS_COLOR: Record<InboundEventStatus, string> = {
  pending:    "bg-blue-100 text-blue-800",
  processing: "bg-amber-100 text-amber-800",
  processed:  "bg-green-100 text-green-800",
  failed:     "bg-red-100 text-red-800",
  duplicate:  "bg-gray-100 text-gray-700",
};

export function InboundEventsTable({ onSelect }: Props) {
  const [status, setStatus] = useState<InboundEventStatus | "">("");
  const { data, isLoading, error } = useInboundEvents({
    status: status || undefined,
    limit: 100,
  });
  const replay = useReplayInboundEvent();
  const [busyId, setBusyId] = useState<string | null>(null);

  async function handleReplay(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    setBusyId(id);
    try {
      await replay.mutateAsync(id);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <header className="flex items-center gap-2 border-b px-3 py-2">
        <label className="text-xs text-muted-foreground">Filtrar por estado:</label>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as InboundEventStatus | "")}
          className="rounded border px-2 py-0.5 text-xs"
        >
          <option value="">Todos</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </header>

      <div className="overflow-auto">
        {isLoading ? (
          <p className="p-4 text-sm text-muted-foreground">Cargando eventos…</p>
        ) : error ? (
          <p className="p-4 text-sm text-red-600">Error al cargar eventos.</p>
        ) : !data || data.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">Sin eventos.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Recibido</th>
                <th className="px-3 py-2 font-medium">Estado</th>
                <th className="px-3 py-2 font-medium">Intentos</th>
                <th className="px-3 py-2 font-medium">Caso</th>
                <th className="px-3 py-2 font-medium">Último error</th>
                <th className="px-3 py-2 font-medium text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {data.map((e) => (
                <tr
                  key={e.id}
                  onClick={() => onSelect(e)}
                  className="cursor-pointer border-b last:border-0 hover:bg-muted/30"
                >
                  <td className="px-3 py-2 font-mono text-xs">
                    {new Date(e.received_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${STATUS_COLOR[e.status]}`}>
                      {e.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {e.attempt_count} / {e.max_attempts}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {e.case_id ? e.case_id.slice(0, 8) : "—"}
                  </td>
                  <td className="max-w-md px-3 py-2 text-xs text-red-700">
                    {e.last_error ? (
                      <span className="line-clamp-1">{e.last_error}</span>
                    ) : "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {e.status === "failed" ? (
                      <button
                        type="button"
                        onClick={(ev) => handleReplay(ev, e.id)}
                        disabled={busyId === e.id}
                        title="Replay este evento"
                        className="inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs hover:bg-muted disabled:opacity-50"
                      >
                        <RefreshCw
                          className={`h-3 w-3 ${busyId === e.id ? "animate-spin" : ""}`}
                        />
                        Replay
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
