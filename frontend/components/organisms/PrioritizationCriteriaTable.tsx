"use client";

import { usePrioritizationCriteria } from "@/hooks/usePrioritization";

const SOURCE_LABEL: Record<string, string> = {
  taxonomy_field: "Campo de taxonomía",
  case_custom_value: "Valor en caso",
  asset_field: "Campo del activo",
  derived: "Calculado",
};

const STRATEGY_LABEL: Record<string, string> = {
  use_default: "Usar valor por defecto",
  skip: "Omitir (renormalizar pesos)",
};

export function PrioritizationCriteriaTable() {
  const { data, isLoading, error } = usePrioritizationCriteria();

  if (isLoading) {
    return <p className="p-4 text-sm text-muted-foreground">Cargando criterios…</p>;
  }
  if (error) {
    return <p className="p-4 text-sm text-red-600">Error al cargar criterios.</p>;
  }
  if (!data || data.length === 0) {
    return (
      <p className="p-4 text-sm text-muted-foreground">
        Sin criterios configurados. Ejecuta las migraciones de prioritization.
      </p>
    );
  }

  return (
    <div className="overflow-auto">
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/40">
          <tr className="text-left">
            <th className="px-3 py-2 font-medium">Código</th>
            <th className="px-3 py-2 font-medium">Nombre</th>
            <th className="px-3 py-2 font-medium">Fuente</th>
            <th className="px-3 py-2 font-medium">Estrategia si falta</th>
            <th className="px-3 py-2 font-medium">Default</th>
            <th className="px-3 py-2 font-medium">Activo</th>
          </tr>
        </thead>
        <tbody>
          {data
            .slice()
            .sort((a, b) => a.sort_order - b.sort_order)
            .map((c) => (
              <tr key={c.id} className="border-b last:border-0 hover:bg-muted/30">
                <td className="px-3 py-2 font-mono text-xs">{c.code}</td>
                <td className="px-3 py-2">{c.name}</td>
                <td className="px-3 py-2 text-xs text-muted-foreground">
                  {SOURCE_LABEL[c.data_source] ?? c.data_source}
                  {c.source_field_key ? (
                    <span className="ml-1 font-mono">({c.source_field_key})</span>
                  ) : null}
                </td>
                <td className="px-3 py-2 text-xs">
                  {STRATEGY_LABEL[c.missing_data_strategy] ?? c.missing_data_strategy}
                </td>
                <td className="px-3 py-2 text-xs">{c.default_value ?? "—"}</td>
                <td className="px-3 py-2 text-xs">
                  {c.is_active ? (
                    <span className="rounded bg-green-100 px-1.5 py-0.5 text-green-800">
                      sí
                    </span>
                  ) : (
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-600">
                      no
                    </span>
                  )}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
