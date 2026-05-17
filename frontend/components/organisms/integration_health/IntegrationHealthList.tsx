"use client";

import {
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  XCircle,
} from "lucide-react";

import { useIntegrationHealth } from "@/hooks/useIntegrationHealth";
import type {
  IntegrationHealthStatus,
  IntegrationHealthSummary,
} from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  selectedId: string | null;
  onSelect: (source: IntegrationHealthSummary) => void;
}

const STATUS_ICON: Record<IntegrationHealthStatus, React.ReactNode> = {
  healthy: <CheckCircle2 className="h-4 w-4 text-green-700" />,
  degraded: <AlertTriangle className="h-4 w-4 text-amber-700" />,
  down: <XCircle className="h-4 w-4 text-red-700" />,
  unknown: <HelpCircle className="h-4 w-4 text-gray-500" />,
};

export function IntegrationHealthList({ selectedId, onSelect }: Props) {
  const { data, isLoading, error } = useIntegrationHealth();

  if (isLoading) {
    return <p className="p-3 text-sm text-muted-foreground">Cargando fuentes…</p>;
  }
  if (error) {
    return <p className="p-3 text-sm text-red-600">Error al cargar.</p>;
  }
  if (!data || data.length === 0) {
    return (
      <p className="rounded border border-dashed p-4 text-sm text-muted-foreground">
        Sin fuentes activas.
      </p>
    );
  }

  return (
    <ul className="space-y-1">
      {data.map((s) => (
        <li key={s.source_id}>
          <button
            type="button"
            onClick={() => onSelect(s)}
            className={cn(
              "flex w-full items-start gap-2 rounded border px-2 py-2 text-left text-xs hover:bg-muted/30",
              selectedId === s.source_id && "border-blue-400 bg-blue-50",
            )}
          >
            {STATUS_ICON[s.status] ?? STATUS_ICON.unknown}
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">
                {s.source_name ?? s.source_id.slice(0, 8)}
              </p>
              <p className="text-muted-foreground">
                recv {s.events_received_5min} · fail{" "}
                <span className={s.events_failed_5min ? "text-red-700" : ""}>
                  {s.events_failed_5min}
                </span>
                {s.avg_latency_ms_5min !== null
                  ? ` · ${s.avg_latency_ms_5min}ms`
                  : null}
              </p>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
