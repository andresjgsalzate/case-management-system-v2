"use client";

import { useIntegrationHealthHistory } from "@/hooks/useIntegrationHealth";
import type {
  IntegrationHealthHistoryPoint,
  IntegrationHealthSummary,
} from "@/lib/types";

interface Props {
  source: IntegrationHealthSummary | null;
  hours?: number;
}

/** Minimal inline SVG line+bar chart — avoids pulling recharts (~50KB).
 *
 * Sub-spec 06 only needs to visualize a single per-source time series of
 * events_received_5min + events_failed_5min over the last few hours.
 * A purpose-built SVG keeps the bundle lean and the rendering deterministic.
 */
export function IntegrationHealthCharts({ source, hours = 6 }: Props) {
  const { data, isLoading } = useIntegrationHealthHistory(
    source?.source_id ?? null, hours,
  );

  if (!source) {
    return (
      <p className="rounded border border-dashed p-6 text-sm text-muted-foreground">
        Selecciona una fuente para ver su historial.
      </p>
    );
  }
  if (isLoading) {
    return <p className="p-3 text-sm">Cargando historial…</p>;
  }
  if (!data || data.length === 0) {
    return (
      <p className="rounded border border-dashed p-4 text-sm text-muted-foreground">
        Sin snapshots para esta fuente en las últimas {hours}h.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <ChartCard
        title={`Eventos recibidos (últimas ${hours}h)`}
        series={data}
        valueKey="events_received_5min"
        color="rgb(37, 99, 235)"
      />
      <ChartCard
        title="Eventos fallidos"
        series={data}
        valueKey="events_failed_5min"
        color="rgb(220, 38, 38)"
      />
      {data.some((p) => p.avg_latency_ms_5min !== null) ? (
        <ChartCard
          title="Latencia promedio (ms)"
          series={data}
          valueKey="avg_latency_ms_5min"
          color="rgb(217, 119, 6)"
        />
      ) : null}
    </div>
  );
}

interface ChartCardProps {
  title: string;
  series: IntegrationHealthHistoryPoint[];
  valueKey: keyof Pick<
    IntegrationHealthHistoryPoint,
    "events_received_5min" | "events_processed_5min" | "events_failed_5min" | "avg_latency_ms_5min"
  >;
  color: string;
}

function ChartCard({ title, series, valueKey, color }: ChartCardProps) {
  // Drop null values for max-scale calc; keep them as 0 in render
  const values = series.map((p) => Number(p[valueKey] ?? 0));
  const max = Math.max(1, ...values);
  const width = 600;
  const height = 100;
  const padding = 4;

  const stepX = (width - padding * 2) / Math.max(1, series.length - 1);
  const points = values
    .map((v, i) => {
      const x = padding + i * stepX;
      const y = padding + (1 - v / max) * (height - padding * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <section className="rounded border bg-card p-3">
      <header className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">{title}</h3>
        <span className="text-xs text-muted-foreground">
          max: {max} · n={series.length}
        </span>
      </header>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-24 w-full"
        preserveAspectRatio="none"
      >
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          points={points}
        />
        {values.map((v, i) => {
          const x = padding + i * stepX;
          const y = padding + (1 - v / max) * (height - padding * 2);
          return (
            <circle key={i} cx={x} cy={y} r="2" fill={color}>
              <title>
                {new Date(series[i].recorded_at).toLocaleString()} → {v}
              </title>
            </circle>
          );
        })}
      </svg>
      <footer className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground">
        <span>{new Date(series[0].recorded_at).toLocaleTimeString()}</span>
        <span>{new Date(series[series.length - 1].recorded_at).toLocaleTimeString()}</span>
      </footer>
    </section>
  );
}
