"use client";

import type { DashboardKPIs } from "@/lib/types";

interface Props {
  kpis: DashboardKPIs;
}

function fmt(value: number | null, suffix: string): string {
  return value === null ? "—" : `${value}${suffix}`;
}

function fmtMinutes(value: number | null): string {
  if (value === null) return "—";
  if (value < 60) return `${Math.round(value)} min`;
  const hours = (value / 60).toFixed(1);
  return `${hours} h`;
}

export function KPIsWidget({ kpis }: Props) {
  return (
    <section className="rounded border bg-card p-3">
      <h3 className="mb-2 text-sm font-semibold">
        KPIs ({kpis.period_hours}h)
      </h3>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3 lg:grid-cols-5">
        <Cell label="MTTR" value={fmtMinutes(kpis.mttr_minutes)} />
        <Cell label="MTTD" value={fmtMinutes(kpis.mttd_minutes)} />
        <Cell label="Casos/hora" value={fmt(kpis.cases_per_hour, "")} />
        <Cell label="SLA compliance" value={fmt(kpis.sla_compliance_pct, " %")} />
        <Cell label="FP rate" value={fmt(kpis.false_positive_rate_pct, " %")} />
      </dl>
    </section>
  );
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border bg-muted/30 px-3 py-2">
      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="font-mono text-lg font-semibold">{value}</dd>
    </div>
  );
}
