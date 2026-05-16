"use client";

import { useMemo } from "react";

import { usePrioritizationFormulas } from "@/hooks/usePrioritization";
import type { PrioritizationFormula } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  selectedId: string | null;
  onSelect: (formula: PrioritizationFormula) => void;
}

export function PrioritizationFormulasList({ selectedId, onSelect }: Props) {
  const { data, isLoading, error } = usePrioritizationFormulas();

  const grouped = useMemo(() => {
    const map = new Map<string, PrioritizationFormula[]>();
    for (const f of data ?? []) {
      const arr = map.get(f.logical_key) ?? [];
      arr.push(f);
      map.set(f.logical_key, arr);
    }
    Array.from(map.values()).forEach((arr) => {
      arr.sort((a: PrioritizationFormula, b: PrioritizationFormula) => b.version - a.version);
    });
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [data]);

  if (isLoading) {
    return <p className="p-3 text-xs text-muted-foreground">Cargando fórmulas…</p>;
  }
  if (error) {
    return <p className="p-3 text-xs text-red-600">Error al cargar fórmulas.</p>;
  }
  if (grouped.length === 0) {
    return <p className="p-3 text-xs text-muted-foreground">Sin fórmulas.</p>;
  }

  return (
    <ul className="space-y-3 p-2">
      {grouped.map(([logicalKey, versions]) => (
        <li key={logicalKey}>
          <h3 className="px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {logicalKey}
          </h3>
          <ul className="mt-1 space-y-1">
            {versions.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  onClick={() => onSelect(f)}
                  className={cn(
                    "flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm hover:bg-muted",
                    selectedId === f.id && "bg-muted font-medium",
                  )}
                >
                  <span className="truncate">
                    v{f.version} — {f.name}
                  </span>
                  {f.is_active ? (
                    <span className="ml-2 shrink-0 rounded bg-green-100 px-1.5 py-0.5 text-[10px] font-medium text-green-800">
                      ACTIVA
                    </span>
                  ) : (
                    <span className="ml-2 shrink-0 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600">
                      v{f.version}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}
