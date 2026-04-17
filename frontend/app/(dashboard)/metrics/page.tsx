"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import { Clock, CheckCircle2, AlertTriangle } from "lucide-react";
import type { DashboardSummary, StatusCount, TrendPoint, ApiResponse } from "@/lib/types";

// ── Types ──────────────────────────────────────────────────────────────────────
interface PriorityCount  { priority_name: string; color: string; count: number }
interface AgentCount     { full_name: string; email: string; assigned_cases: number }
interface AppCount       { application: string; count: number }
interface SlaCompliance  { total: number; breached: number; met: number; compliance_pct: number }
interface ResolutionTime { avg_minutes: number; avg_hours: number }

// ── Hooks ──────────────────────────────────────────────────────────────────────
function useMetrics() {
  const q = <T,>(key: string[], url: string) =>
    useQuery<T>({
      queryKey: key,
      queryFn: async () => {
        const { data } = await apiClient.get<ApiResponse<T>>(url);
        return data.data as T;
      },
    });

  return {
    dashboard:      q<DashboardSummary>(["metrics","dashboard"],    "/metrics/dashboard"),
    byStatus:       q<StatusCount[]>   (["metrics","by-status"],    "/metrics/cases/by-status"),
    byPriority:     q<PriorityCount[]> (["metrics","by-priority"],  "/metrics/cases/by-priority"),
    trend:          q<TrendPoint[]>    (["metrics","trend"],         "/metrics/cases/trend"),
    byAgent:        q<AgentCount[]>    (["metrics","by-agent"],      "/metrics/cases/by-agent"),
    byApp:          q<AppCount[]>      (["metrics","by-app"],        "/metrics/cases/by-application"),
    sla:            q<SlaCompliance>   (["metrics","sla"],           "/metrics/sla/compliance"),
    resolution:     q<ResolutionTime>  (["metrics","resolution"],    "/metrics/resolution-time"),
  };
}

// ── Color helpers ──────────────────────────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  abierto: "bg-blue-500", open: "bg-blue-500",
  en_progreso: "bg-amber-500", in_progress: "bg-amber-500",
  pendiente: "bg-orange-500", pending: "bg-orange-500",
  resuelto: "bg-emerald-500", resolved: "bg-emerald-500",
  cerrado: "bg-gray-400", closed: "bg-gray-400",
};

function statusColor(name: string) {
  const key = (name ?? "").toLowerCase().replace(/\s+/g, "_");
  return STATUS_COLORS[key] ?? "bg-gray-400";
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatCard({ label, value, accent, sub }: { label: string; value: string | number; accent: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 relative overflow-hidden">
      <div className={`absolute top-0 left-0 w-1 h-full ${accent}`} />
      <p className="text-xs text-muted-foreground pl-3">{label}</p>
      <p className="text-3xl font-bold text-foreground pl-3 mt-1 tabular-nums">{value}</p>
      {sub && <p className="text-xs text-muted-foreground pl-3 mt-0.5">{sub}</p>}
    </div>
  );
}

function Panel({ title, loading, empty, children }: {
  title: string; loading: boolean; empty: boolean; children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5 flex flex-col gap-4">
      <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      {loading ? (
        <div className="flex justify-center py-6"><Spinner /></div>
      ) : empty ? (
        <p className="text-sm text-muted-foreground text-center py-6">Sin datos</p>
      ) : children}
    </div>
  );
}

// color puede ser clase Tailwind ("bg-blue-500") o hex ("#3B82F6")
function BarList({ items }: { items: { label: string; count: number; color: string }[] }) {
  const total = items.reduce((a, b) => a + b.count, 0);

  function dotStyle(color: string) {
    return color.startsWith("#")
      ? { style: { backgroundColor: color } as React.CSSProperties, className: "h-2.5 w-2.5 rounded-full shrink-0" }
      : { style: undefined, className: `h-2.5 w-2.5 rounded-full shrink-0 ${color}` };
  }
  function barStyle(color: string, pct: number) {
    return color.startsWith("#")
      ? { style: { width: `${pct}%`, backgroundColor: color } as React.CSSProperties, className: "h-full rounded-full transition-all duration-500" }
      : { style: { width: `${pct}%` } as React.CSSProperties, className: `h-full rounded-full transition-all duration-500 ${color}` };
  }

  return (
    <div className="flex flex-col gap-4">
      {items.map((item) => {
        const pct = total ? Math.round((item.count / total) * 100) : 0;
        const dot = dotStyle(item.color);
        const bar = barStyle(item.color, pct);
        return (
          <div key={item.label} className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className={dot.className} style={dot.style} />
                <span className="text-sm font-medium text-foreground truncate">{item.label}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0 text-xs text-muted-foreground">
                <span className="font-semibold text-foreground tabular-nums">{item.count}</span>
                <span>({pct}%)</span>
              </div>
            </div>
            <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
              <div className={bar.className} style={bar.style} />
            </div>
          </div>
        );
      })}
      <div className="pt-1 border-t border-border flex justify-between text-xs text-muted-foreground">
        <span>Total</span>
        <span className="font-semibold text-foreground tabular-nums">{total} casos</span>
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────
export default function MetricsPage() {
  usePermissionGuard("metrics", "read");
  const { dashboard, byStatus, byPriority, trend, byAgent, byApp, sla, resolution } = useMetrics();

  const d           = dashboard.data;
  const statuses    = (byStatus.data   ?? []) as StatusCount[];
  const priorities  = (byPriority.data ?? []) as PriorityCount[];
  const trendData   = (trend.data      ?? []) as TrendPoint[];
  const agents      = (byAgent.data    ?? []) as AgentCount[];
  const apps        = (byApp.data      ?? []) as AppCount[];
  const slaData     = sla.data         as SlaCompliance | undefined;
  const resData     = resolution.data  as ResolutionTime | undefined;

  const maxTrend = Math.max(...trendData.map((t) => t.count), 1);

  function fmtMinutes(min: number) {
    if (min < 60) return `${min} min`;
    if (min < 1440) return `${Math.round(min / 60)} h`;
    return `${Math.round(min / 1440)} días`;
  }

  if (dashboard.isLoading) {
    return <div className="flex justify-center py-16"><Spinner size="lg" /></div>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Resumen de actividad del sistema</p>
      </div>

      {/* ── Fila 1: KPI cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Casos abiertos"  value={d?.open_cases ?? 0}    accent="bg-blue-500" />
        <StatCard label="Creados hoy"     value={d?.created_today ?? 0}  accent="bg-emerald-500" />
        <StatCard label="Resueltos hoy"   value={d?.resolved_today ?? 0} accent="bg-violet-500" />
        <StatCard label="Sin asignar"     value={d?.unassigned ?? 0}     accent="bg-amber-500" />
      </div>

      {/* ── Fila 2: SLA + Tiempo resolución ── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* SLA compliance */}
        <div className="rounded-lg border border-border bg-card p-5 flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-foreground">Cumplimiento SLA</h2>
          {sla.isLoading ? <Spinner /> : !slaData ? (
            <p className="text-sm text-muted-foreground">Sin datos</p>
          ) : (
            <>
              <div className="flex items-end gap-2">
                <span className="text-4xl font-bold tabular-nums text-foreground">{slaData.compliance_pct}%</span>
                {slaData.compliance_pct >= 90
                  ? <CheckCircle2 className="h-5 w-5 text-emerald-500 mb-1" />
                  : <AlertTriangle className="h-5 w-5 text-amber-500 mb-1" />}
              </div>
              <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${slaData.compliance_pct >= 90 ? "bg-emerald-500" : slaData.compliance_pct >= 70 ? "bg-amber-500" : "bg-red-500"}`}
                  style={{ width: `${slaData.compliance_pct}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span className="text-emerald-600">{slaData.met} cumplidos</span>
                <span className="text-red-600">{slaData.breached} incumplidos</span>
              </div>
            </>
          )}
        </div>

        {/* Tiempo promedio resolución */}
        <div className="rounded-lg border border-border bg-card p-5 flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-foreground">Tiempo promedio resolución</h2>
          {resolution.isLoading ? <Spinner /> : !resData ? (
            <p className="text-sm text-muted-foreground">Sin datos</p>
          ) : (
            <>
              <div className="flex items-end gap-2">
                <span className="text-4xl font-bold tabular-nums text-foreground">{fmtMinutes(resData.avg_minutes)}</span>
                <Clock className="h-5 w-5 text-muted-foreground mb-1" />
              </div>
              <p className="text-xs text-muted-foreground">
                Promedio desde creación hasta cierre de los casos resueltos
              </p>
            </>
          )}
        </div>

        {/* Tendencia 30 días */}
        <div className="rounded-lg border border-border bg-card p-5 flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-foreground">Tendencia (30 días)</h2>
          {trend.isLoading ? (
            <div className="flex justify-center py-6"><Spinner /></div>
          ) : trendData.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">Sin datos</p>
          ) : (
            <div className="flex items-end gap-0.5 h-20 mt-auto">
              {trendData.map((point, i) => {
                const height = Math.max(4, (point.count / maxTrend) * 100);
                return (
                  <div
                    key={i}
                    className="flex-1 bg-primary/60 hover:bg-primary rounded-t transition-colors cursor-default"
                    style={{ height: `${height}%` }}
                    title={`${point.date}: ${point.count} casos`}
                  />
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Fila 3: Por estado + Por prioridad ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Casos por estado" loading={byStatus.isLoading} empty={statuses.length === 0}>
          <BarList items={statuses.map((s) => ({
            label: s.status ?? "Sin estado",
            count: s.count,
            color: statusColor(s.status ?? ""),
          }))} />
        </Panel>

        <Panel title="Casos por prioridad" loading={byPriority.isLoading} empty={priorities.length === 0}>
          <BarList items={priorities.map((p) => ({
            label: p.priority_name,
            count: p.count,
            color: p.color ?? "bg-gray-400",
          }))} />
        </Panel>
      </div>

      {/* ── Fila 4: Por agente + Por aplicación ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Por agente */}
        <Panel title="Carga por agente" loading={byAgent.isLoading} empty={agents.length === 0}>
          <div className="flex flex-col gap-3">
            {agents.map((a, i) => {
              const max = agents[0]?.assigned_cases ?? 1;
              const pct = Math.round((a.assigned_cases / max) * 100);
              return (
                <div key={a.email} className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-bold text-muted-foreground">
                        {i + 1}
                      </span>
                      <span className="text-sm font-medium text-foreground truncate">{a.full_name}</span>
                    </div>
                    <span className="text-xs font-semibold text-foreground tabular-nums shrink-0">
                      {a.assigned_cases} casos
                    </span>
                  </div>
                  <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                    <div className="h-full rounded-full bg-primary/70 transition-all duration-500" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>

        {/* Por aplicación */}
        <Panel title="Casos por aplicación" loading={byApp.isLoading} empty={apps.length === 0}>
          <BarList items={apps.map((a, i) => {
            const COLORS = ["bg-violet-500","bg-cyan-500","bg-rose-500","bg-teal-500","bg-orange-500","bg-indigo-500"];
            return { label: a.application, count: a.count, color: COLORS[i % COLORS.length] };
          })} />
        </Panel>
      </div>
    </div>
  );
}
