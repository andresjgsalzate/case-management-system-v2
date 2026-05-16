"use client";

import { X } from "lucide-react";
import { useState } from "react";

import {
  useCreateFormulaVersion,
  usePrioritizationCriteria,
} from "@/hooks/usePrioritization";
import type { PrioritizationFormula } from "@/lib/types";

interface Props {
  isOpen: boolean;
  /** When provided, the new formula is a v(N+1) of this base. */
  baseFormula?: PrioritizationFormula | null;
  onClose: () => void;
  onCreated?: (created: PrioritizationFormula) => void;
}

const DEFAULT_PRIORITIES = ["Baja", "Media", "Alta", "Critica"] as const;

type WeightRow = { code: string; weight: string };
type ThresholdRow = { min_value: string; max_value: string; priority_name: string };

const INITIAL_THRESHOLDS: ThresholdRow[] = [
  { min_value: "0.00", max_value: "2.49", priority_name: "Baja" },
  { min_value: "2.50", max_value: "3.49", priority_name: "Media" },
  { min_value: "3.50", max_value: "4.49", priority_name: "Alta" },
  { min_value: "4.50", max_value: "5.00", priority_name: "Critica" },
];

export function CreateFormulaModal({
  isOpen,
  baseFormula,
  onClose,
  onCreated,
}: Props) {
  const { data: criteria } = usePrioritizationCriteria();
  const create = useCreateFormulaVersion();

  const [logicalKey, setLogicalKey] = useState(baseFormula?.logical_key ?? "");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [weights, setWeights] = useState<WeightRow[]>([]);
  const [thresholds, setThresholds] = useState<ThresholdRow[]>(INITIAL_THRESHOLDS);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const weightSum = weights.reduce((acc, w) => acc + Number(w.weight || 0), 0);

  function addWeight() {
    setWeights((w) => [...w, { code: "", weight: "0" }]);
  }

  function updateWeight(idx: number, patch: Partial<WeightRow>) {
    setWeights((w) =>
      w.map((row, i) => (i === idx ? { ...row, ...patch } : row)),
    );
  }

  function removeWeight(idx: number) {
    setWeights((w) => w.filter((_, i) => i !== idx));
  }

  function updateThreshold(idx: number, patch: Partial<ThresholdRow>) {
    setThresholds((t) =>
      t.map((row, i) => (i === idx ? { ...row, ...patch } : row)),
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg(null);

    if (!logicalKey.trim() || !name.trim()) {
      setErrorMsg("logical_key y name son requeridos");
      return;
    }
    if (weights.length === 0) {
      setErrorMsg("Agrega al menos un criterio");
      return;
    }
    if (Math.abs(weightSum - 1) > 0.001) {
      setErrorMsg(`Los pesos deben sumar 1.00 (suma actual: ${weightSum.toFixed(3)})`);
      return;
    }

    try {
      const created = await create.mutateAsync({
        tenant_id: null,
        logical_key: logicalKey.trim(),
        base_version_id: baseFormula?.id ?? null,
        name: name.trim(),
        description: description.trim() || null,
        criteria_weights: weights,
        thresholds,
      });
      onCreated?.(created);
      onClose();
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Error desconocido al crear fórmula";
      setErrorMsg(msg);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-lg bg-card shadow-xl">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-base font-semibold">
            {baseFormula ? `Nueva versión de ${baseFormula.logical_key}` : "Nueva fórmula"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <form onSubmit={handleSubmit} className="space-y-4 p-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="mb-1 block font-medium">logical_key *</span>
              <input
                type="text"
                value={logicalKey}
                onChange={(e) => setLogicalKey(e.target.value)}
                disabled={Boolean(baseFormula)}
                className="w-full rounded border px-2 py-1 text-sm font-mono"
                placeholder="ej: soc-default"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium">Nombre *</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded border px-2 py-1 text-sm"
              />
            </label>
          </div>

          <label className="block text-sm">
            <span className="mb-1 block font-medium">Descripción</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full rounded border px-2 py-1 text-sm"
            />
          </label>

          <section>
            <header className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold">
                Pesos por criterio{" "}
                <span className="font-normal text-muted-foreground">
                  (suma: {weightSum.toFixed(2)})
                </span>
              </h3>
              <button
                type="button"
                onClick={addWeight}
                className="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:bg-blue-700"
              >
                + Criterio
              </button>
            </header>
            <div className="space-y-1">
              {weights.map((w, i) => (
                <div key={i} className="flex items-center gap-2">
                  <select
                    value={w.code}
                    onChange={(e) => updateWeight(i, { code: e.target.value })}
                    className="flex-1 rounded border px-2 py-1 text-sm"
                  >
                    <option value="">— Selecciona criterio —</option>
                    {(criteria ?? []).map((c) => (
                      <option key={c.id} value={c.code}>
                        {c.code} — {c.name}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    max="1"
                    value={w.weight}
                    onChange={(e) => updateWeight(i, { weight: e.target.value })}
                    className="w-24 rounded border px-2 py-1 text-right text-sm font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => removeWeight(i)}
                    className="rounded p-1 text-red-600 hover:bg-red-50"
                    aria-label="Eliminar"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
              {weights.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Sin criterios. Haz clic en &quot;+ Criterio&quot;.
                </p>
              ) : null}
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold">Umbrales</h3>
            <div className="space-y-1">
              {thresholds.map((t, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    type="number"
                    step="0.01"
                    value={t.min_value}
                    onChange={(e) => updateThreshold(i, { min_value: e.target.value })}
                    className="w-20 rounded border px-2 py-1 text-right text-sm font-mono"
                  />
                  <span className="text-xs text-muted-foreground">—</span>
                  <input
                    type="number"
                    step="0.01"
                    value={t.max_value}
                    onChange={(e) => updateThreshold(i, { max_value: e.target.value })}
                    className="w-20 rounded border px-2 py-1 text-right text-sm font-mono"
                  />
                  <span className="text-xs text-muted-foreground">→</span>
                  <select
                    value={t.priority_name}
                    onChange={(e) =>
                      updateThreshold(i, { priority_name: e.target.value })
                    }
                    className="flex-1 rounded border px-2 py-1 text-sm"
                  >
                    {DEFAULT_PRIORITIES.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </section>

          {errorMsg ? (
            <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
              {errorMsg}
            </p>
          ) : null}

          <footer className="flex justify-end gap-2 border-t pt-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded border px-3 py-1.5 text-sm hover:bg-muted"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={create.isPending}
              className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {create.isPending ? "Guardando…" : "Crear fórmula"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
