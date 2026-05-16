"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";

import {
  useCasePriorityCalculations,
  useFormulaDetail,
  useRecalculatePriority,
} from "@/hooks/usePrioritization";
import { useHasPermission } from "@/hooks/useHasPermission";
import type { PriorityCalculation } from "@/lib/types";

const TRIGGER_LABEL: Record<string, string> = {
  case_created: "Creación del caso",
  case_updated: "Cambio en el caso",
  manual: "Manual",
  formula_promoted: "Promoción a nueva versión",
  scheduled: "Programado",
};

interface Props {
  caseId: string;
}

export function PriorityCalculationBreakdown({ caseId }: Props) {
  const { data: history, isLoading, error } = useCasePriorityCalculations(caseId, 10);
  const recalc = useRecalculatePriority();
  const canRecalculate = useHasPermission("prioritization", "recalculate");
  const [actionError, setActionError] = useState<string | null>(null);

  const latest: PriorityCalculation | undefined = history?.[0];

  // Pull formula detail to map criterion codes → names (for the inputs breakdown).
  const { data: formulaDetail } = useFormulaDetail(latest?.formula_id ?? null);

  async function handleRecalculate() {
    setActionError(null);
    try {
      await recalc.mutateAsync(caseId);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Error al recalcular");
    }
  }

  if (isLoading) {
    return <p className="p-4 text-sm text-muted-foreground">Cargando cálculos…</p>;
  }
  if (error) {
    return <p className="p-4 text-sm text-red-600">Error al cargar cálculos.</p>;
  }
  if (!history || history.length === 0) {
    return (
      <div className="space-y-3 p-4">
        <p className="text-sm text-muted-foreground">
          No hay cálculos de prioridad registrados para este caso.
        </p>
        {canRecalculate ? (
          <button
            type="button"
            onClick={handleRecalculate}
            disabled={recalc.isPending}
            className="inline-flex items-center gap-1.5 rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${recalc.isPending ? "animate-spin" : ""}`} />
            Calcular prioridad
          </button>
        ) : null}
        {actionError ? (
          <p className="text-sm text-red-600">{actionError}</p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4">
      <section>
        <header className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Último cálculo</h3>
          {canRecalculate && latest ? (
            <button
              type="button"
              onClick={handleRecalculate}
              disabled={recalc.isPending}
              className="inline-flex items-center gap-1.5 rounded border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
              title="Recalcular prioridad con la fórmula activa actual"
            >
              <RefreshCw
                className={`h-3 w-3 ${recalc.isPending ? "animate-spin" : ""}`}
              />
              Recalcular
            </button>
          ) : null}
        </header>

        {latest ? (
          <LatestCalculationPanel
            calculation={latest}
            criterionNames={
              formulaDetail
                ? Object.fromEntries(
                    formulaDetail.criteria_weights.map((w) => [
                      w.criterion_code,
                      w.criterion_name,
                    ]),
                  )
                : {}
            }
            formulaName={formulaDetail?.name ?? null}
            formulaLogicalKey={formulaDetail?.logical_key ?? null}
          />
        ) : null}

        {actionError ? (
          <p className="mt-2 text-sm text-red-600">{actionError}</p>
        ) : null}
      </section>

      {history.length > 1 ? (
        <section>
          <h3 className="mb-2 text-sm font-semibold">
            Histórico ({history.length - 1}{" "}
            {history.length - 1 === 1 ? "cálculo anterior" : "cálculos anteriores"})
          </h3>
          <ol className="space-y-1">
            {history.slice(1).map((calc) => (
              <li
                key={calc.id}
                className="flex items-center justify-between rounded border px-3 py-2 text-xs"
              >
                <div>
                  <span className="font-mono">
                    {new Date(calc.calculated_at).toLocaleString()}
                  </span>
                  <span className="ml-2 text-muted-foreground">
                    · {TRIGGER_LABEL[calc.triggered_by] ?? calc.triggered_by}
                  </span>
                </div>
                <div className="font-mono">
                  Σ = {Number(calc.weighted_sum).toFixed(2)} · v{calc.formula_version}
                </div>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}

interface LatestProps {
  calculation: PriorityCalculation;
  criterionNames: Record<string, string>;
  formulaName: string | null;
  formulaLogicalKey: string | null;
}

function LatestCalculationPanel({
  calculation,
  criterionNames,
  formulaName,
  formulaLogicalKey,
}: LatestProps) {
  const inputs = calculation.inputs as Record<string, unknown>;
  const inputEntries = Object.entries(inputs).filter(
    ([key]) => !key.startsWith("_"), // _meta keys hidden
  );

  return (
    <div className="space-y-3 rounded border bg-muted/20 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-xs text-muted-foreground">
            Fórmula:{" "}
            <span className="font-mono">
              {formulaLogicalKey ?? calculation.formula_id}
            </span>{" "}
            v{calculation.formula_version}
            {formulaName ? <span className="ml-1">— {formulaName}</span> : null}
          </p>
          <p className="text-xs text-muted-foreground">
            {TRIGGER_LABEL[calculation.triggered_by] ?? calculation.triggered_by} ·{" "}
            {new Date(calculation.calculated_at).toLocaleString()}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Suma ponderada
          </p>
          <p className="font-mono text-lg font-semibold">
            {Number(calculation.weighted_sum).toFixed(2)}
          </p>
        </div>
      </div>

      {inputEntries.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Valores por criterio
          </p>
          <table className="w-full text-xs">
            <thead className="border-b">
              <tr className="text-left">
                <th className="py-1 font-medium">Criterio</th>
                <th className="py-1 text-right font-medium">Valor (1-5)</th>
              </tr>
            </thead>
            <tbody>
              {inputEntries.map(([code, value]) => (
                <tr key={code} className="border-b last:border-0">
                  <td className="py-1">
                    {criterionNames[code] ?? code}{" "}
                    <span className="font-mono text-muted-foreground">({code})</span>
                  </td>
                  <td className="py-1 text-right font-mono">{String(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
