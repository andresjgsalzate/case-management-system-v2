"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import type { DashboardSummary, StatusCount, TrendPoint, ApiResponse } from "@/lib/types";

function useMetrics() {
  const dashboard = useQuery({
    queryKey: ["metrics", "dashboard"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<DashboardSummary>>("/metrics/dashboard");
      return data.data;
    },
  });
  const byStatus = useQuery({
    queryKey: ["metrics", "by-status"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<StatusCount[]>>("/metrics/cases/by-status");
      return data.data ?? [];
    },
  });
  const trend = useQuery({
    queryKey: ["metrics", "trend"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<TrendPoint[]>>("/metrics/cases/trend");
      return data.data ?? [];
    },
  });
  return { dashboard, byStatus, trend };
}

const STATUS_COLORS: Record<string, string> = {
  open: "bg-blue-500",
  in_progress: "bg-amber-500",
  pending: "bg-orange-500",
  resolved: "bg-emerald-500",
  closed: "bg-gray-400",
};

export default function MetricsPage() {
  const { dashboard, byStatus, trend } = useMetrics();
  const d = dashboard.data;
  const statuses = byStatus.data ?? [];
  const trendData = trend.data ?? [];
  const maxTrend = Math.max(...trendData.map((t) => t.count), 1);

  if (dashboard.isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Métricas</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Resumen de actividad del sistema</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Casos abiertos" value={d?.open_cases ?? 0} accent="bg-blue-500" />
        <StatCard label="Creados hoy" value={d?.created_today ?? 0} accent="bg-emerald-500" />
        <StatCard label="Resueltos hoy" value={d?.resolved_today ?? 0} accent="bg-violet-500" />
        <StatCard label="Sin asignar" value={d?.unassigned ?? 0} accent="bg-amber-500" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* By status */}
        <div className="rounded-lg border border-border bg-card p-5">
          <h2 className="text-sm font-semibold text-foreground mb-4">Casos por estado</h2>
          {byStatus.isLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : statuses.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">Sin datos</p>
          ) : (
            <div className="flex flex-col gap-3">
              {statuses.map((s) => {
                const total = statuses.reduce((a, b) => a + b.count, 0);
                const pct = total ? Math.round((s.count / total) * 100) : 0;
                const colorKey = s.status.toLowerCase().replace(/\s+/g, "_");
                const color = STATUS_COLORS[colorKey] ?? "bg-gray-400";
                return (
                  <div key={s.status} className="flex items-center gap-3">
                    <div className="w-24 text-xs text-muted-foreground truncate text-right shrink-0">
                      {s.status}
                    </div>
                    <div className="flex-1 h-5 bg-muted rounded overflow-hidden">
                      <div
                        className={`h-full rounded ${color} transition-all duration-500`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-muted-foreground w-8 text-right shrink-0">
                      {s.count}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Trend */}
        <div className="rounded-lg border border-border bg-card p-5">
          <h2 className="text-sm font-semibold text-foreground mb-4">Tendencia (30 días)</h2>
          {trend.isLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : trendData.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">Sin datos</p>
          ) : (
            <div className="flex items-end gap-0.5 h-32">
              {trendData.map((point, i) => {
                const height = maxTrend ? Math.max(2, (point.count / maxTrend) * 100) : 2;
                return (
                  <div
                    key={i}
                    className="flex-1 bg-primary/70 hover:bg-primary rounded-t transition-colors cursor-default group relative"
                    style={{ height: `${height}%` }}
                    title={`${point.date}: ${point.count} casos`}
                  />
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 relative overflow-hidden">
      <div className={`absolute top-0 left-0 w-1 h-full ${accent}`} />
      <p className="text-xs text-muted-foreground pl-3">{label}</p>
      <p className="text-3xl font-bold text-foreground pl-3 mt-1">{value.toLocaleString()}</p>
    </div>
  );
}
