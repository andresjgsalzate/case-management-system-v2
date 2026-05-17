"use client";

import { useState } from "react";

import { IntegrationHealthCharts } from "@/components/organisms/integration_health/IntegrationHealthCharts";
import { IntegrationHealthList } from "@/components/organisms/integration_health/IntegrationHealthList";
import type { IntegrationHealthSummary } from "@/lib/types";

export default function IntegrationHealthPage() {
  const [selected, setSelected] =
    useState<IntegrationHealthSummary | null>(null);
  const [hours, setHours] = useState<number>(6);

  return (
    <div className="space-y-4 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold">Salud de integraciones</h1>
        <p className="text-sm text-muted-foreground">
          Estado per-fuente cada 5 minutos. Historial actualizado por el job
          de fondo cada 60s.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="space-y-2 rounded border bg-card p-2">
          <header className="text-xs font-semibold uppercase text-muted-foreground">
            Fuentes
          </header>
          <IntegrationHealthList
            selectedId={selected?.source_id ?? null}
            onSelect={setSelected}
          />
        </aside>

        <main className="space-y-3">
          <div className="flex items-center gap-2 rounded border bg-card p-2 text-xs">
            <label className="flex items-center gap-1">
              Ventana:
              <select
                value={hours}
                onChange={(e) => setHours(Number(e.target.value))}
                className="rounded border px-2 py-0.5"
                disabled={!selected}
              >
                <option value={1}>1 hora</option>
                <option value={6}>6 horas</option>
                <option value={24}>24 horas</option>
                <option value={72}>3 días</option>
                <option value={168}>7 días</option>
              </select>
            </label>
            {selected ? (
              <span className="ml-auto text-muted-foreground">
                {selected.source_name ?? selected.source_id}
              </span>
            ) : null}
          </div>

          <IntegrationHealthCharts source={selected} hours={hours} />
        </main>
      </div>
    </div>
  );
}
