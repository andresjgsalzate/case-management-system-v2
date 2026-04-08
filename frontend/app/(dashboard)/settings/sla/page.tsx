"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, AlertTriangle, CheckCircle } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import type { ApiResponse } from "@/lib/types";

interface SLAPolicy {
  id: string;
  priority_id: string;
  priority?: { name: string; level: number; color: string };
  target_response_hours?: number;
  target_resolution_hours: number;
  is_active?: boolean;
}

function useSLAPolicies() {
  return useQuery({
    queryKey: ["sla-policies"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<SLAPolicy[]>>("/sla/policies");
      return data.data ?? [];
    },
  });
}

function hoursLabel(h: number) {
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  const rem = h % 24;
  return rem ? `${d}d ${rem}h` : `${d}d`;
}

const URGENCY_ICON: Record<number, typeof Clock> = {
  1: Clock,
  2: Clock,
  3: AlertTriangle,
  4: AlertTriangle,
};

export default function SLASettingsPage() {
  const { data: policies = [], isLoading } = useSLAPolicies();

  const sorted = [...policies].sort(
    (a, b) => (a.priority?.level ?? 0) - (b.priority?.level ?? 0)
  );

  return (
    <div className="flex flex-col gap-5 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Políticas SLA</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Plazos de resolución por prioridad de caso
        </p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      )}

      {!isLoading && policies.length === 0 && (
        <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
          <Clock className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p className="text-sm">No hay políticas SLA configuradas</p>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {sorted.map((policy) => {
          const Icon = URGENCY_ICON[policy.priority?.level ?? 1] ?? Clock;
          const color = policy.priority?.color ?? "#6B7280";
          const resH = policy.target_resolution_hours;
          const urgent = resH <= 4;

          return (
            <div
              key={policy.id}
              className="rounded-lg border border-border bg-card p-4 flex items-center gap-4"
            >
              <div
                className="h-10 w-10 rounded-md flex items-center justify-center shrink-0"
                style={{ backgroundColor: color + "20" }}
              >
                <Icon className="h-5 w-5" style={{ color }} />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-foreground">
                    {policy.priority?.name ?? "Sin prioridad"}
                  </span>
                  {urgent && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-destructive/10 text-destructive">
                      Urgente
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Resolución objetivo: <strong className="text-foreground">{hoursLabel(resH)}</strong>
                  {policy.target_response_hours && (
                    <> · Respuesta: <strong className="text-foreground">{hoursLabel(policy.target_response_hours)}</strong></>
                  )}
                </p>
              </div>

              <div className="shrink-0">
                {policy.is_active !== false ? (
                  <div className="flex items-center gap-1 text-xs text-success">
                    <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                    <span className="text-green-600 dark:text-green-400">Activa</span>
                  </div>
                ) : (
                  <span className="text-xs text-muted-foreground">Inactiva</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
