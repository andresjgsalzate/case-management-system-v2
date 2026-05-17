"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";

import type { AuditEvent, AuditQueryResultDTO } from "@/lib/types";

interface Props {
  result: AuditQueryResultDTO | undefined;
  isLoading: boolean;
  error: unknown;
}

const SOURCE_COLOR: Record<string, string> = {
  activity:      "bg-blue-100 text-blue-800",
  audit:         "bg-purple-100 text-purple-800",
  inbound_event: "bg-amber-100 text-amber-800",
};

export function AuditExplorerResults({ result, isLoading, error }: Props) {
  if (isLoading) {
    return <p className="p-3 text-sm">Cargando eventos…</p>;
  }
  if (error) {
    return <p className="p-3 text-sm text-red-600">Error al cargar.</p>;
  }
  if (!result) {
    return (
      <p className="rounded border border-dashed p-6 text-sm text-muted-foreground">
        Aplica filtros y presiona Buscar para ver eventos.
      </p>
    );
  }
  if (result.events.length === 0) {
    return (
      <p className="rounded border border-dashed p-6 text-sm text-muted-foreground">
        Sin eventos para estos filtros.
      </p>
    );
  }

  return (
    <div>
      <p className="mb-2 text-xs text-muted-foreground">
        {result.events.length} de {result.total} eventos
      </p>
      <ul className="space-y-1">
        {result.events.map((e) => (
          <AuditRow key={`${e.source_table}-${e.event_id}`} event={e} />
        ))}
      </ul>
    </div>
  );
}

function AuditRow({ event }: { event: AuditEvent }) {
  const [expanded, setExpanded] = useState(false);
  const cls = SOURCE_COLOR[event.source_table] ?? "bg-gray-100 text-gray-700";

  return (
    <li className="rounded border bg-card">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-start gap-2 px-2 py-2 text-left text-xs hover:bg-muted/30"
      >
        <ChevronRight
          className={`h-3 w-3 shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
        />
        <span
          className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${cls}`}
        >
          {event.source_table}
        </span>
        <span className="min-w-0 flex-1 truncate font-mono">
          {event.summary}
        </span>
        <span className="shrink-0 text-muted-foreground">
          {new Date(event.occurred_at).toLocaleString()}
        </span>
      </button>
      {expanded ? (
        <div className="space-y-2 border-t bg-muted/20 p-3 text-xs">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
            <dt className="font-medium text-muted-foreground">Caso</dt>
            <dd className="font-mono">{event.case_id ?? "—"}</dd>
            <dt className="font-medium text-muted-foreground">Actor</dt>
            <dd className="font-mono">{event.actor_id ?? "—"}</dd>
            <dt className="font-medium text-muted-foreground">Event ID</dt>
            <dd className="break-all font-mono">{event.event_id}</dd>
          </dl>
          {event.extra ? (
            <div>
              <p className="font-medium">Payload</p>
              <pre className="overflow-auto rounded bg-card p-2 text-[10px]">
                {JSON.stringify(event.extra, null, 2)}
              </pre>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
