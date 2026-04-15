"use client";

import { useState, useEffect } from "react";
import { Check, ChevronDown } from "lucide-react";
import {
  useClassification,
  useClassificationCriteria,
  useClassificationThresholds,
  useSaveClassification,
  type ClassificationCriterion,
} from "@/hooks/useCases";
import { formatDate } from "@/lib/utils";

interface CaseClassificationProps {
  caseId: string;
}

const LEVEL_STYLES: Record<string, { label: string; className: string }> = {
  baja:  { label: "BAJA",  className: "bg-green-100 text-green-800 border-green-200" },
  media: { label: "MEDIA", className: "bg-yellow-100 text-yellow-800 border-yellow-200" },
  alta:  { label: "ALTA",  className: "bg-red-100 text-red-800 border-red-200" },
};

const SCORE_DOT: Record<number, string> = {
  1: "bg-green-500",
  2: "bg-yellow-500",
  3: "bg-red-500",
};

function complexityLevel(total: number, lowMax: number, mediumMax: number): string {
  if (total === 0) return "";
  if (total <= lowMax) return "baja";
  if (total <= mediumMax) return "media";
  return "alta";
}

// ── Accordion item ──────────────────────────────────────────────────────────

function CriterionAccordion({
  criterion,
  score,
  index,
  open,
  onToggle,
  onChange,
}: {
  criterion: ClassificationCriterion;
  score: number | undefined;
  index: number;
  open: boolean;
  onToggle: () => void;
  onChange: (v: number) => void;
}) {
  const options = [
    { value: 1 as const, description: criterion.score1_description },
    { value: 2 as const, description: criterion.score2_description },
    { value: 3 as const, description: criterion.score3_description },
  ];

  return (
    <div className={`rounded-lg border transition-colors ${open ? "border-primary/40 bg-card" : "border-border bg-card"}`}>
      {/* Header — siempre visible */}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        {/* Número / check */}
        <span
          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
            score !== undefined
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground"
          }`}
        >
          {score !== undefined ? <Check className="h-3 w-3" /> : index + 1}
        </span>

        <span className="flex-1 text-sm font-medium text-foreground">{criterion.name}</span>

        {/* Puntaje seleccionado */}
        {score !== undefined && !open && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className={`h-2 w-2 rounded-full ${SCORE_DOT[score]}`} />
            {score} pt
          </span>
        )}

        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {/* Opciones — colapsables */}
      {open && (
        <div className="flex flex-col gap-1.5 border-t border-border px-4 pb-4 pt-3">
          {options.map(({ value, description }) => (
            <button
              key={value}
              type="button"
              onClick={() => onChange(value)}
              className={`flex items-start gap-3 w-full rounded-md border px-3 py-2.5 text-left transition-colors ${
                score === value
                  ? "border-primary bg-primary/5 text-foreground"
                  : "border-border bg-background text-muted-foreground hover:border-primary/40 hover:bg-muted/50"
              }`}
            >
              <span
                className={`shrink-0 mt-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 text-xs font-bold ${
                  score === value
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border"
                }`}
              >
                {value}
              </span>
              <span className="text-sm leading-relaxed">{description}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Read-only view ──────────────────────────────────────────────────────────

function ClassificationReadOnly({
  cls,
  criteria,
  thresholds,
}: {
  cls: NonNullable<ReturnType<typeof useClassification>["data"]>;
  criteria: ClassificationCriterion[];
  thresholds: { low_max: number; medium_max: number };
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const activeCriteria = criteria.filter((c) => c.is_active);
  const level = cls.complexity_level ?? "";
  const levelStyle = level ? LEVEL_STYLES[level] : null;

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Clasificación registrada</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Clasificado el {formatDate(cls.classified_at)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-lg font-bold text-foreground tabular-nums">{cls.total_score}</span>
            <span className="text-xs text-muted-foreground">/ {activeCriteria.length * 3} pts</span>
          </div>
          {levelStyle && (
            <span className={`rounded-md border px-2.5 py-1 text-xs font-bold tracking-wide ${levelStyle.className}`}>
              {levelStyle.label}
            </span>
          )}
        </div>
      </div>

      {/* Read-only accordion */}
      <div className="flex flex-col gap-2">
        {activeCriteria.map((criterion, index) => {
          const score = cls.scores?.[criterion.id];
          const isOpen = openId === criterion.id;
          const options = [
            { value: 1, description: criterion.score1_description },
            { value: 2, description: criterion.score2_description },
            { value: 3, description: criterion.score3_description },
          ];
          return (
            <div key={criterion.id} className={`rounded-lg border transition-colors ${isOpen ? "border-primary/40 bg-card" : "border-border bg-card"}`}>
              <button
                type="button"
                onClick={() => setOpenId(isOpen ? null : criterion.id)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left"
              >
                <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${score !== undefined ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
                  {score !== undefined ? <Check className="h-3 w-3" /> : index + 1}
                </span>
                <span className="flex-1 text-sm font-medium text-foreground">{criterion.name}</span>
                {score !== undefined && !isOpen && (
                  <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className={`h-2 w-2 rounded-full ${SCORE_DOT[score as 1|2|3]}`} />
                    {score} pt
                  </span>
                )}
                <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
              </button>
              {isOpen && (
                <div className="flex flex-col gap-1.5 border-t border-border px-4 pb-4 pt-3">
                  {options.map(({ value, description }) => (
                    <div
                      key={value}
                      className={`flex items-start gap-3 rounded-md border px-3 py-2.5 ${
                        score === value
                          ? "border-primary bg-primary/5 text-foreground"
                          : "border-border bg-background text-muted-foreground opacity-50"
                      }`}
                    >
                      <span className={`shrink-0 mt-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 text-xs font-bold ${score === value ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>
                        {value}
                      </span>
                      <span className="text-sm leading-relaxed">{description}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Leyenda */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-green-500" />BAJA 1-{thresholds.low_max}</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-yellow-500" />MEDIA {thresholds.low_max + 1}-{thresholds.medium_max}</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-red-500" />ALTA {thresholds.medium_max + 1}-{activeCriteria.length * 3}</span>
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

export function CaseClassification({ caseId }: CaseClassificationProps) {
  const { data: cls, isLoading: clsLoading } = useClassification(caseId);
  const { data: criteria = [], isLoading: criteriaLoading } = useClassificationCriteria();
  const { data: thresholds = { low_max: 6, medium_max: 11 } } = useClassificationThresholds();
  const save = useSaveClassification(caseId);

  const [scores, setScores] = useState<Record<string, number>>({});
  const [openId, setOpenId] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const activeCriteria = criteria.filter((c) => c.is_active);

  useEffect(() => {
    if (cls?.scores) {
      setScores(cls.scores);
    }
  }, [cls]);

  useEffect(() => {
    if (activeCriteria.length > 0 && openId === null && !cls) {
      const first = activeCriteria.find((c) => !scores[c.id]);
      setOpenId(first?.id ?? activeCriteria[0].id);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCriteria.length, cls]);

  const total = Object.values(scores).reduce((a, b) => a + b, 0);
  const allAnswered = activeCriteria.length > 0 && activeCriteria.every((c) => scores[c.id] !== undefined);
  const level = complexityLevel(total, thresholds.low_max, thresholds.medium_max);
  const levelStyle = level ? LEVEL_STYLES[level] : null;

  function handleChange(criterionId: string, value: number) {
    const updated = { ...scores, [criterionId]: value };
    setScores(updated);
    const nextUnanswered = activeCriteria.find((c) => c.id !== criterionId && updated[c.id] === undefined);
    setOpenId(nextUnanswered?.id ?? null);
  }

  async function handleSave() {
    await save.mutateAsync(scores);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  if (clsLoading || criteriaLoading) {
    return <p className="text-sm text-muted-foreground text-center py-8">Cargando…</p>;
  }

  if (activeCriteria.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-8">
        No hay criterios configurados. Un administrador debe hacerlo en{" "}
        <strong>Configuración → Rúbrica de clasificación</strong>.
      </p>
    );
  }

  // ── Si ya está clasificado: solo lectura ──
  if (cls) {
    return (
      <ClassificationReadOnly cls={cls} criteria={criteria} thresholds={thresholds} />
    );
  }

  const answeredCount = activeCriteria.filter((c) => scores[c.id] !== undefined).length;

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Tabulación por puntos</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {answeredCount}/{activeCriteria.length} criterios respondidos
          </p>
        </div>

        <div className="flex items-center gap-3">
          {total > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="text-lg font-bold text-foreground tabular-nums">{total}</span>
              <span className="text-xs text-muted-foreground">/ {activeCriteria.length * 3} pts</span>
            </div>
          )}
          {levelStyle && (
            <span className={`rounded-md border px-2.5 py-1 text-xs font-bold tracking-wide ${levelStyle.className}`}>
              {levelStyle.label}
            </span>
          )}
        </div>
      </div>

      {/* Accordion */}
      <div className="flex flex-col gap-2">
        {activeCriteria.map((criterion, index) => (
          <CriterionAccordion
            key={criterion.id}
            criterion={criterion}
            score={scores[criterion.id]}
            index={index}
            open={openId === criterion.id}
            onToggle={() => setOpenId(openId === criterion.id ? null : criterion.id)}
            onChange={(v) => handleChange(criterion.id, v)}
          />
        ))}
      </div>

      {/* Leyenda de rangos */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-green-500" />BAJA 1-{thresholds.low_max}</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-yellow-500" />MEDIA {thresholds.low_max + 1}-{thresholds.medium_max}</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-red-500" />ALTA {thresholds.medium_max + 1}-{activeCriteria.length * 3}</span>
      </div>

      {/* Guardar */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={!allAnswered || save.isPending}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saved ? <><Check className="h-3.5 w-3.5" />Guardado</> : "Guardar clasificación"}
        </button>
      </div>
    </div>
  );
}
