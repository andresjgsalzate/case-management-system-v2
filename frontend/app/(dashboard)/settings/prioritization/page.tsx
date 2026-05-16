"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { CreateFormulaModal } from "@/components/organisms/CreateFormulaModal";
import { PrioritizationCriteriaTable } from "@/components/organisms/PrioritizationCriteriaTable";
import { PrioritizationFormulaDetail } from "@/components/organisms/PrioritizationFormulaDetail";
import { PrioritizationFormulasList } from "@/components/organisms/PrioritizationFormulasList";
import type { PrioritizationFormula } from "@/lib/types";

export default function PrioritizationSettingsPage() {
  const [selectedFormula, setSelectedFormula] =
    useState<PrioritizationFormula | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [baseFormula, setBaseFormula] = useState<PrioritizationFormula | null>(null);

  function openCreate() {
    setBaseFormula(null);
    setCreateOpen(true);
  }

  function openNewVersion() {
    if (!selectedFormula) return;
    setBaseFormula(selectedFormula);
    setCreateOpen(true);
  }

  return (
    <div className="space-y-4 p-4">
      <header>
        <h1 className="text-xl font-semibold">Motor de Priorización</h1>
        <p className="text-sm text-muted-foreground">
          Configura criterios y fórmulas para calcular la prioridad de los casos.
        </p>
      </header>

      <section className="rounded border bg-card">
        <header className="border-b px-3 py-2">
          <h2 className="text-sm font-semibold">Criterios disponibles</h2>
        </header>
        <PrioritizationCriteriaTable />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        <div className="flex flex-col overflow-hidden rounded border bg-card">
          <header className="flex items-center justify-between border-b px-3 py-2">
            <h2 className="text-sm font-semibold">Fórmulas</h2>
            <div className="flex gap-1">
              {selectedFormula ? (
                <button
                  type="button"
                  onClick={openNewVersion}
                  className="rounded border px-2 py-1 text-xs hover:bg-muted"
                  title="Nueva versión basada en la fórmula seleccionada"
                >
                  + Versión
                </button>
              ) : null}
              <button
                type="button"
                onClick={openCreate}
                className="inline-flex items-center gap-1 rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
              >
                <Plus className="h-3.5 w-3.5" /> Nueva
              </button>
            </div>
          </header>
          <div className="flex-1 overflow-auto">
            <PrioritizationFormulasList
              selectedId={selectedFormula?.id ?? null}
              onSelect={setSelectedFormula}
            />
          </div>
        </div>

        <div className="overflow-auto rounded border bg-card">
          <PrioritizationFormulaDetail formulaId={selectedFormula?.id ?? null} />
        </div>
      </section>

      <CreateFormulaModal
        isOpen={createOpen}
        baseFormula={baseFormula}
        onClose={() => setCreateOpen(false)}
        onCreated={(f) => setSelectedFormula(f)}
      />
    </div>
  );
}
