"use client";

import { useCallback, useState } from "react";

import { useDashboardStream } from "@/hooks/useDashboardStream";

type LiveEvent = {
  id: string;
  receivedAt: number;
  eventType: string;
  summary: string;
};

const MAX_EVENTS = 100;

function _summarize(eventType: string, payload: unknown): string {
  if (typeof payload !== "object" || payload === null) return eventType;
  const p = payload as Record<string, unknown>;
  // Common fields that show up in most events
  const caseId = p.case_id ?? p.caseId;
  const sourceName = p.source_name ?? p.source_id;
  if (caseId) return `${eventType} · case ${String(caseId).slice(0, 8)}`;
  if (sourceName) return `${eventType} · ${String(sourceName).slice(0, 32)}`;
  return eventType;
}

export function LiveEventsStreamWidget() {
  const [events, setEvents] = useState<LiveEvent[]>([]);

  const handleEvent = useCallback(
    (eventType: string, payload: unknown) => {
      const entry: LiveEvent = {
        id: crypto.randomUUID(),
        receivedAt: Date.now(),
        eventType,
        summary: _summarize(eventType, payload),
      };
      setEvents((prev) => [entry, ...prev].slice(0, MAX_EVENTS));
    },
    [],
  );

  const { connected, staleMs } = useDashboardStream(handleEvent);

  return (
    <section className="rounded border bg-card p-3">
      <header className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Eventos en vivo</h3>
        <StreamIndicator connected={connected} staleMs={staleMs} />
      </header>

      {events.length === 0 ? (
        <p className="rounded border border-dashed p-3 text-xs text-muted-foreground">
          Esperando eventos…
        </p>
      ) : (
        <ol className="max-h-96 space-y-1 overflow-auto">
          {events.map((e) => (
            <li
              key={e.id}
              className="flex items-center justify-between gap-2 rounded border px-2 py-1 text-[11px]"
            >
              <span className="truncate font-mono">{e.summary}</span>
              <span className="shrink-0 text-muted-foreground">
                {new Date(e.receivedAt).toLocaleTimeString()}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function StreamIndicator({
  connected, staleMs,
}: { connected: boolean; staleMs: number }) {
  // Heartbeat fires every 30s server-side; consider stalled if no heartbeat
  // in 90s (2 missed pulses + slack).
  const stalled = staleMs > 90_000;
  const color = !connected || stalled
    ? "bg-red-500"
    : staleMs > 60_000
    ? "bg-amber-500"
    : "bg-green-500";
  const label = !connected
    ? "desconectado"
    : stalled
    ? "stream estancado"
    : "en vivo";
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
      <span className={`inline-block h-2 w-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}
