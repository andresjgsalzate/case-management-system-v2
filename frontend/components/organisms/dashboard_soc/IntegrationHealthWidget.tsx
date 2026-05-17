"use client";

import { AlertTriangle, CheckCircle2, HelpCircle, XCircle } from "lucide-react";

import type {
  IntegrationHealthStatus,
  IntegrationHealthSummary,
} from "@/lib/types";

interface Props {
  sources: IntegrationHealthSummary[] | null;
}

const STATUS_ICON: Record<IntegrationHealthStatus, React.ReactNode> = {
  healthy: <CheckCircle2 className="h-4 w-4 text-green-700" />,
  degraded: <AlertTriangle className="h-4 w-4 text-amber-700" />,
  down: <XCircle className="h-4 w-4 text-red-700" />,
  unknown: <HelpCircle className="h-4 w-4 text-gray-500" />,
};

export function IntegrationHealthWidget({ sources }: Props) {
  // Hidden if actor lacks integration_health:read (backend returns null)
  if (sources === null) return null;

  return (
    <section className="rounded border bg-card p-3">
      <h3 className="mb-2 text-sm font-semibold">Salud de integraciones</h3>
      {sources.length === 0 ? (
        <p className="rounded border border-dashed p-3 text-xs text-muted-foreground">
          Sin fuentes configuradas.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {sources.map((s) => (
            <li
              key={s.source_id}
              className="flex items-center gap-2 rounded border px-2 py-1.5 text-xs"
            >
              {STATUS_ICON[s.status] ?? STATUS_ICON.unknown}
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{s.source_name ?? s.source_id.slice(0, 8)}</p>
                <p className="text-muted-foreground">
                  recibidos {s.events_received_5min} ·
                  fallidos <span className={s.events_failed_5min ? "text-red-700" : ""}>
                    {" "}{s.events_failed_5min}
                  </span>
                  {s.avg_latency_ms_5min !== null
                    ? ` · ${s.avg_latency_ms_5min}ms`
                    : null}
                </p>
              </div>
              <span className="text-[10px] text-muted-foreground">
                {new Date(s.recorded_at).toLocaleTimeString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
