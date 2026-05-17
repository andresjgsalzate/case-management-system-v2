"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";

import { useInboundEvents } from "@/hooks/useInboundEvents";
import type { InboundEvent } from "@/lib/types";

interface Props {
  caseId: string;
}

/** Lists inbound_events linked to the current case. Backend doesn't yet
 * accept case_id filter on /inbound-events, so we filter client-side from
 * the most recent 200 events. */
export function WazuhEventsTab({ caseId }: Props) {
  const { data, isLoading, error } = useInboundEvents({ limit: 200 });

  const events = (data ?? []).filter((e) => e.case_id === caseId);

  if (isLoading) {
    return <p className="p-3 text-sm">Cargando eventos…</p>;
  }
  if (error) {
    return <p className="p-3 text-sm text-red-600">Error al cargar eventos.</p>;
  }
  if (events.length === 0) {
    return (
      <p className="rounded border border-dashed p-6 text-sm text-muted-foreground">
        Sin eventos de integración vinculados a este caso.
      </p>
    );
  }
  return (
    <ul className="space-y-1">
      {events.map((e) => (
        <WazuhEventRow key={e.id} event={e} />
      ))}
    </ul>
  );
}

const STATUS_COLOR: Record<string, string> = {
  pending: "bg-blue-100 text-blue-800",
  processing: "bg-amber-100 text-amber-800",
  processed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  duplicate: "bg-gray-100 text-gray-700",
};

function WazuhEventRow({ event }: { event: InboundEvent }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li className="rounded border bg-card">
      <button
        type="button"
        onClick={() => setExpanded((x) => !x)}
        className="flex w-full items-center gap-2 px-2 py-2 text-left text-xs hover:bg-muted/30"
      >
        <ChevronRight
          className={`h-3 w-3 transition-transform ${expanded ? "rotate-90" : ""}`}
        />
        <span
          className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${STATUS_COLOR[event.status] ?? "bg-gray-100 text-gray-700"}`}
        >
          {event.status}
        </span>
        <span className="font-mono">{event.idempotency_key.slice(0, 16)}</span>
        <span className="ml-auto text-muted-foreground">
          {new Date(event.received_at).toLocaleString()}
        </span>
      </button>
      {expanded ? (
        <div className="border-t bg-muted/20 p-3 text-xs">
          {event.last_error ? (
            <pre className="mb-2 overflow-auto rounded bg-red-50 p-2 text-red-900">
              {event.last_error}
            </pre>
          ) : null}
          <pre className="max-h-80 overflow-auto rounded bg-card p-2">
            {JSON.stringify(event.raw_payload, null, 2)}
          </pre>
        </div>
      ) : null}
    </li>
  );
}
