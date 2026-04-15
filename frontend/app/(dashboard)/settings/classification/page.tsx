"use client";

import { useState, useEffect } from "react";
import { Plus, Trash2, ChevronUp, ChevronDown, Save } from "lucide-react";
import {
  useClassificationCriteria,
  useClassificationThresholds,
  useCreateCriterion,
  useUpdateCriterion,
  useDeleteCriterion,
  useUpdateThresholds,
  type ClassificationCriterion,
} from "@/hooks/useCases";
import { Spinner } from "@/components/atoms/Spinner";
import { useConfirm } from "@/components/providers/ConfirmProvider";

// ── Criterion Editor ──────────────────────────────────────────────────────────

function CriterionEditor({
  criterion,
  canMoveUp,
  canMoveDown,
  onMoveUp,
  onMoveDown,
  onDelete,
}: {
  criterion: ClassificationCriterion;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDelete: () => void;
}) {
  const update = useUpdateCriterion();
  const [name, setName] = useState(criterion.name);
  const [s1, setS1] = useState(criterion.score1_description);
  const [s2, setS2] = useState(criterion.score2_description);
  const [s3, setS3] = useState(criterion.score3_description);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setName(criterion.name);
    setS1(criterion.score1_description);
    setS2(criterion.score2_description);
    setS3(criterion.score3_description);
    setDirty(false);
  }, [criterion]);

  function markDirty() { setDirty(true); }

  async function handleSave() {
    await update.mutateAsync({ id: criterion.id, name, score1_description: s1, score2_description: s2, score3_description: s3 });
    setDirty(false);
  }

  return (
    <div className="rounded-lg border border-border bg-card">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <div className="flex flex-col gap-0.5">
          <button onClick={onMoveUp} disabled={!canMoveUp} className="text-muted-foreground hover:text-foreground disabled:opacity-30">
            <ChevronUp className="h-3.5 w-3.5" />
          </button>
          <button onClick={onMoveDown} disabled={!canMoveDown} className="text-muted-foreground hover:text-foreground disabled:opacity-30">
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
        </div>
        <input
          value={name}
          onChange={(e) => { setName(e.target.value); markDirty(); }}
          className="flex-1 bg-transparent text-sm font-medium text-foreground focus:outline-none"
          placeholder="Nombre del criterio…"
        />
        {dirty && (
          <button
            onClick={handleSave}
            disabled={update.isPending}
            className="inline-flex items-center gap-1 rounded bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <Save className="h-3 w-3" />
            Guardar
          </button>
        )}
        <button
          onClick={onDelete}
          className="text-muted-foreground hover:text-destructive transition-colors"
          title="Eliminar criterio"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      {/* Score descriptions */}
      <div className="flex flex-col gap-3 p-4">
        {(
          [
            { label: "1 PUNTO", value: s1, onChange: (v: string) => { setS1(v); markDirty(); } },
            { label: "2 PUNTOS", value: s2, onChange: (v: string) => { setS2(v); markDirty(); } },
            { label: "3 PUNTOS", value: s3, onChange: (v: string) => { setS3(v); markDirty(); } },
          ] as const
        ).map(({ label, value, onChange }) => (
          <div key={label} className="flex items-start gap-3">
            <span className="shrink-0 mt-2 rounded bg-muted px-1.5 py-0.5 text-[11px] font-semibold text-muted-foreground w-16 text-center">
              {label}
            </span>
            <textarea
              value={value}
              onChange={(e) => onChange(e.target.value)}
              rows={2}
              className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
              placeholder={`Descripción para ${label}…`}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ClassificationSettingsPage() {
  const confirm = useConfirm();
  const { data: criteria = [], isLoading } = useClassificationCriteria();
  const { data: thresholds = { low_max: 6, medium_max: 11 } } = useClassificationThresholds();
  const createCriterion = useCreateCriterion();
  const deleteCriterion = useDeleteCriterion();
  const updateCriterion = useUpdateCriterion();
  const updateThresholds = useUpdateThresholds();

  const [lowMax, setLowMax] = useState(thresholds.low_max);
  const [mediumMax, setMediumMax] = useState(thresholds.medium_max);
  const [thresholdDirty, setThresholdDirty] = useState(false);

  useEffect(() => {
    setLowMax(thresholds.low_max);
    setMediumMax(thresholds.medium_max);
    setThresholdDirty(false);
  }, [thresholds]);

  const activeCriteria = criteria.filter((c) => c.is_active);
  const maxPossible = activeCriteria.length * 3;

  async function handleAddCriterion() {
    const nextOrder = activeCriteria.length > 0
      ? Math.max(...activeCriteria.map((c) => c.order)) + 1
      : 1;
    await createCriterion.mutateAsync({
      name: "Nuevo criterio",
      score1_description: "",
      score2_description: "",
      score3_description: "",
      order: nextOrder,
    });
  }

  async function handleMove(criterion: ClassificationCriterion, direction: "up" | "down") {
    const sorted = [...activeCriteria].sort((a, b) => a.order - b.order);
    const idx = sorted.findIndex((c) => c.id === criterion.id);
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= sorted.length) return;
    const swap = sorted[swapIdx];
    await Promise.all([
      updateCriterion.mutateAsync({ id: criterion.id, order: swap.order }),
      updateCriterion.mutateAsync({ id: swap.id, order: criterion.order }),
    ]);
  }

  async function handleDelete(id: string) {
    const ok = await confirm({ description: "¿Eliminar este criterio? Esta acción no se puede deshacer." });
    if (!ok) return;
    await deleteCriterion.mutateAsync(id);
  }

  async function handleSaveThresholds() {
    await updateThresholds.mutateAsync({ low_max: lowMax, medium_max: mediumMax });
    setThresholdDirty(false);
  }

  const sorted = [...activeCriteria].sort((a, b) => a.order - b.order);

  return (
    <div className="flex flex-col gap-7">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">Rúbrica de clasificación</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Configura los criterios de tabulación por puntos para determinar la complejidad de los casos.
        </p>
      </div>

      {/* Criteria */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-foreground">
            Criterios de evaluación
            <span className="ml-2 text-xs text-muted-foreground">({sorted.length} criterios)</span>
          </p>
          <button
            onClick={handleAddCriterion}
            disabled={createCriterion.isPending}
            className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:border-primary transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Agregar criterio
          </button>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : sorted.length === 0 ? (
          <p className="text-sm text-muted-foreground italic text-center py-8">
            No hay criterios configurados. Agrega el primero.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {sorted.map((criterion, index) => (
              <CriterionEditor
                key={criterion.id}
                criterion={criterion}
                canMoveUp={index > 0}
                canMoveDown={index < sorted.length - 1}
                onMoveUp={() => handleMove(criterion, "up")}
                onMoveDown={() => handleMove(criterion, "down")}
                onDelete={() => handleDelete(criterion.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Thresholds */}
      <div className="rounded-lg border border-border bg-card p-5 flex flex-col gap-4">
        <div>
          <p className="text-sm font-medium text-foreground">Umbrales de complejidad</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Puntaje máximo: <strong>{maxPossible}</strong> ({sorted.length} criterios × 3 puntos)
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <span className="h-2 w-2 rounded-full bg-green-500" />
              Tope BAJA (1 a ?)
            </label>
            <input
              type="number"
              min="1"
              max={mediumMax - 1}
              value={lowMax}
              onChange={(e) => { setLowMax(Number(e.target.value)); setThresholdDirty(true); }}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <span className="h-2 w-2 rounded-full bg-yellow-500" />
              Tope MEDIA ({lowMax + 1} a ?)
            </label>
            <input
              type="number"
              min={lowMax + 1}
              max={maxPossible - 1}
              value={mediumMax}
              onChange={(e) => { setMediumMax(Number(e.target.value)); setThresholdDirty(true); }}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
        </div>

        {/* Preview */}
        <div className="flex items-center gap-3 text-xs flex-wrap">
          <span className="px-2 py-1 rounded bg-green-100 text-green-800 border border-green-200 font-medium">
            BAJA: 1–{lowMax} pts
          </span>
          <span className="px-2 py-1 rounded bg-yellow-100 text-yellow-800 border border-yellow-200 font-medium">
            MEDIA: {lowMax + 1}–{mediumMax} pts
          </span>
          <span className="px-2 py-1 rounded bg-red-100 text-red-800 border border-red-200 font-medium">
            ALTA: {mediumMax + 1}–{maxPossible} pts
          </span>
        </div>

        {thresholdDirty && (
          <div className="flex justify-end">
            <button
              onClick={handleSaveThresholds}
              disabled={updateThresholds.isPending || lowMax >= mediumMax}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              Guardar umbrales
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
