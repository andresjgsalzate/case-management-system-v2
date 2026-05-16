"use client";

import { useFormulaDetail } from "@/hooks/usePrioritization";

const PRIORITY_COLOR: Record<string, string> = {
  Baja: "bg-blue-100 text-blue-800",
  Media: "bg-yellow-100 text-yellow-800",
  Alta: "bg-orange-100 text-orange-800",
  Critica: "bg-red-100 text-red-800",
};

interface Props {
  formulaId: string | null;
}

export function PrioritizationFormulaDetail({ formulaId }: Props) {
  const { data, isLoading, error } = useFormulaDetail(formulaId);

  if (!formulaId) {
    return (
      <p className="p-4 text-sm text-muted-foreground">
        Selecciona una fórmula para ver sus pesos y umbrales.
      </p>
    );
  }
  if (isLoading) return <p className="p-4 text-sm">Cargando fórmula…</p>;
  if (error) return <p className="p-4 text-sm text-red-600">Error al cargar.</p>;
  if (!data) return null;

  const weightTotal = data.criteria_weights.reduce(
    (acc, w) => acc + Number(w.weight),
    0,
  );

  return (
    <div className="space-y-4 p-4">
      <header>
        <h2 className="text-lg font-semibold">{data.name}</h2>
        <p className="text-xs text-muted-foreground">
          {data.logical_key} · v{data.version} ·{" "}
          {data.is_active ? (
            <span className="font-medium text-green-700">ACTIVA</span>
          ) : (
            <span className="text-muted-foreground">superseded</span>
          )}
          {data.tenant_id === null ? " · global" : ` · tenant ${data.tenant_id}`}
        </p>
        {data.description ? (
          <p className="mt-2 text-sm">{data.description}</p>
        ) : null}
      </header>

      <section>
        <h3 className="mb-1 text-sm font-semibold">
          Pesos por criterio{" "}
          <span className="font-normal text-muted-foreground">
            (suma: {weightTotal.toFixed(2)})
          </span>
        </h3>
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/40 text-left">
            <tr>
              <th className="px-2 py-1.5 font-medium">Criterio</th>
              <th className="px-2 py-1.5 font-medium">Código</th>
              <th className="px-2 py-1.5 text-right font-medium">Peso</th>
            </tr>
          </thead>
          <tbody>
            {data.criteria_weights.map((w) => (
              <tr key={w.criterion_id} className="border-b last:border-0">
                <td className="px-2 py-1.5">{w.criterion_name}</td>
                <td className="px-2 py-1.5 font-mono text-xs">{w.criterion_code}</td>
                <td className="px-2 py-1.5 text-right font-mono">
                  {Number(w.weight).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h3 className="mb-1 text-sm font-semibold">Umbrales → Prioridad</h3>
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/40 text-left">
            <tr>
              <th className="px-2 py-1.5 font-medium">Rango (suma ponderada)</th>
              <th className="px-2 py-1.5 font-medium">Prioridad asignada</th>
            </tr>
          </thead>
          <tbody>
            {data.thresholds.map((t) => (
              <tr key={t.id} className="border-b last:border-0">
                <td className="px-2 py-1.5 font-mono text-xs">
                  [{Number(t.min_value).toFixed(2)} — {Number(t.max_value).toFixed(2)}]
                </td>
                <td className="px-2 py-1.5">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      PRIORITY_COLOR[t.priority_name] ?? "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {t.priority_name}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <footer className="text-xs text-muted-foreground">
        Creada {new Date(data.created_at).toLocaleString()}
      </footer>
    </div>
  );
}
