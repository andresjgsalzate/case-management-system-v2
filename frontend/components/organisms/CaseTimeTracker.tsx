"use client";

import { useState, useEffect, useRef } from "react";
import { Play, Square, Clock, Plus, Trash2, AlertCircle } from "lucide-react";
import {
  useActiveTimer,
  useTimeEntries,
  useStartTimer,
  useStopTimer,
  useManualTimeEntry,
  useDeleteTimeEntry,
  useClassification,
  useSLAIntegrationConfig,
} from "@/hooks/useCases";
import { formatRelative } from "@/lib/utils";

interface CaseTimeTrackerProps {
  caseId: string;
}

function formatMinutes(total: number): string {
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function CaseTimeTracker({ caseId }: CaseTimeTrackerProps) {
  const { data: activeTimer } = useActiveTimer();
  const { data: timeData, isLoading } = useTimeEntries(caseId);
  const startTimer = useStartTimer(caseId);
  const stopTimer = useStopTimer(caseId);
  const addManual = useManualTimeEntry(caseId);
  const deleteEntry = useDeleteTimeEntry(caseId);
  const { data: classification } = useClassification(caseId);
  const { data: slaConfig } = useSLAIntegrationConfig();

  // Cronómetro local
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Estado para detener timer (descripción)
  const [showStopForm, setShowStopForm] = useState(false);
  const [stopDescription, setStopDescription] = useState("");

  // Estado para entrada manual
  const [showManualForm, setShowManualForm] = useState(false);
  const [manualHours, setManualHours] = useState("");
  const [manualMinutes, setManualMinutes] = useState("");
  const [manualDescription, setManualDescription] = useState("");

  const isMyTimer = activeTimer?.case_id === caseId;
  const isOtherTimer = !!activeTimer && activeTimer.case_id !== caseId;

  // Sincronizar cronómetro con el timer activo
  useEffect(() => {
    if (isMyTimer && activeTimer) {
      const startMs = new Date(activeTimer.started_at).getTime();
      const update = () => {
        const diff = Math.floor((Date.now() - startMs) / 1000);
        setElapsed(diff);
      };
      update();
      intervalRef.current = setInterval(update, 1000);
    } else {
      setElapsed(0);
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isMyTimer, activeTimer]);

  async function handleStart() {
    await startTimer.mutateAsync();
  }

  async function handleStop() {
    if (!stopDescription.trim()) return;
    await stopTimer.mutateAsync(stopDescription.trim());
    setShowStopForm(false);
    setStopDescription("");
  }

  async function handleManualSubmit() {
    const h = parseInt(manualHours || "0", 10);
    const m = parseInt(manualMinutes || "0", 10);
    const total = h * 60 + m;
    if (total <= 0 || !manualDescription.trim()) return;
    await addManual.mutateAsync({
      minutes: total,
      description: manualDescription.trim(),
    });
    setManualHours("");
    setManualMinutes("");
    setManualDescription("");
    setShowManualForm(false);
  }

  const entries = timeData?.entries ?? [];
  const totalMinutes = timeData?.total_minutes ?? 0;

  // Max hours limit logic
  const maxHoursForLevel =
    slaConfig?.enabled && classification?.complexity_level
      ? {
          baja: slaConfig.low_max_hours,
          media: slaConfig.medium_max_hours,
          alta: slaConfig.high_max_hours,
        }[classification.complexity_level.toLowerCase() as "baja" | "media" | "alta"] ?? null
      : null;

  const maxMinutes = maxHoursForLevel !== null ? Math.floor(maxHoursForLevel * 60) : null;
  const usedPct = maxMinutes ? Math.min(100, (totalMinutes / maxMinutes) * 100) : null;
  const isAtLimit = maxMinutes !== null && totalMinutes >= maxMinutes;
  const isNearLimit = !isAtLimit && usedPct !== null && usedPct >= 80;

  return (
    <div className="flex flex-col gap-5">
      {/* Timer header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">
            Total registrado:{" "}
            <span className="font-semibold text-primary">{formatMinutes(totalMinutes)}</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isMyTimer && (
            <span className="font-mono text-lg font-semibold text-primary tabular-nums">
              {formatElapsed(elapsed)}
            </span>
          )}

          {isOtherTimer && (
            <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-2 py-1">
              <AlertCircle className="h-3.5 w-3.5" />
              Timer activo en otro caso
            </div>
          )}

          {!isMyTimer && !isOtherTimer && (
            <button
              onClick={handleStart}
              disabled={startTimer.isPending}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              <Play className="h-3.5 w-3.5" />
              Iniciar timer
            </button>
          )}

          {isMyTimer && !showStopForm && (
            <button
              onClick={() => setShowStopForm(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 transition-colors"
            >
              <Square className="h-3.5 w-3.5" />
              Detener
            </button>
          )}
        </div>
      </div>

      {/* Max hours warning */}
      {maxMinutes !== null && (
        <div className={`rounded-md border p-3 flex flex-col gap-2 ${
          isAtLimit
            ? "bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-900"
            : isNearLimit
            ? "bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-900"
            : "bg-muted/30 border-border"
        }`}>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <AlertCircle className={`h-3.5 w-3.5 ${isAtLimit ? "text-red-600" : isNearLimit ? "text-amber-600" : "text-muted-foreground"}`} />
              <span className={`text-xs font-medium ${isAtLimit ? "text-red-600" : isNearLimit ? "text-amber-600" : "text-muted-foreground"}`}>
                {isAtLimit
                  ? "Límite de horas alcanzado"
                  : isNearLimit
                  ? "Cerca del límite de horas"
                  : `Límite: ${formatMinutes(maxMinutes)} (${classification?.complexity_level?.toUpperCase()})`}
              </span>
            </div>
            <span className={`text-xs font-semibold tabular-nums ${isAtLimit ? "text-red-600" : isNearLimit ? "text-amber-600" : "text-foreground"}`}>
              {formatMinutes(totalMinutes)} / {formatMinutes(maxMinutes)}
            </span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-black/10 dark:bg-white/10 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${isAtLimit ? "bg-red-500" : isNearLimit ? "bg-amber-500" : "bg-primary/60"}`}
              style={{ width: `${usedPct ?? 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Stop form */}
      {showStopForm && (
        <div className="rounded-md border border-border bg-muted/30 p-4 flex flex-col gap-3">
          <p className="text-sm font-medium text-foreground">¿Qué hiciste en este tiempo?</p>
          <textarea
            autoFocus
            value={stopDescription}
            onChange={(e) => setStopDescription(e.target.value)}
            placeholder="Describe la actividad realizada…"
            rows={3}
            className="flex w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
          />
          {!stopDescription.trim() && (
            <p className="text-xs text-destructive">La descripción es obligatoria</p>
          )}
          <div className="flex justify-end gap-2">
            <button
              onClick={() => { setShowStopForm(false); setStopDescription(""); }}
              className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground border border-border rounded-md transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={handleStop}
              disabled={stopTimer.isPending || !stopDescription.trim()}
              className="inline-flex items-center gap-1.5 rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50 transition-colors"
            >
              <Square className="h-3.5 w-3.5" />
              Detener y guardar
            </button>
          </div>
        </div>
      )}

      {/* Manual entry */}
      <div>
        {!showManualForm ? (
          <button
            onClick={() => setShowManualForm(true)}
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground border border-dashed border-border rounded-md px-3 py-1.5 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Agregar tiempo manual
          </button>
        ) : (
          <div className="rounded-md border border-border bg-muted/30 p-4 flex flex-col gap-3">
            <p className="text-sm font-medium text-foreground">Agregar tiempo manual</p>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min="0"
                  value={manualHours}
                  onChange={(e) => setManualHours(e.target.value)}
                  placeholder="0"
                  className="w-16 rounded-md border border-border bg-background px-2 py-1.5 text-sm text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <span className="text-xs text-muted-foreground">h</span>
              </div>
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min="0"
                  max="59"
                  value={manualMinutes}
                  onChange={(e) => setManualMinutes(e.target.value)}
                  placeholder="0"
                  className="w-16 rounded-md border border-border bg-background px-2 py-1.5 text-sm text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <span className="text-xs text-muted-foreground">min</span>
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <input
                type="text"
                value={manualDescription}
                onChange={(e) => setManualDescription(e.target.value)}
                placeholder="Descripción de la actividad…"
                className="flex w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              {!manualDescription.trim() && (
                <p className="text-xs text-destructive">La descripción es obligatoria</p>
              )}
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShowManualForm(false); setManualHours(""); setManualMinutes(""); setManualDescription(""); }}
                className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground border border-border rounded-md transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleManualSubmit}
                disabled={
                  addManual.isPending ||
                  (parseInt(manualHours || "0") === 0 && parseInt(manualMinutes || "0") === 0) ||
                  !manualDescription.trim()
                }
                className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                Guardar
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Entries list */}
      {isLoading ? (
        <p className="text-sm text-muted-foreground text-center py-4">Cargando registros…</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-muted-foreground italic text-center py-4">Sin registros de tiempo todavía.</p>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Historial</p>
          {entries.map((entry) => (
            <div
              key={entry.id}
              className="flex items-start justify-between rounded-md border border-border bg-muted/20 px-3 py-2.5 group"
            >
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <span
                  className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[11px] font-medium ${
                    entry.entry_type === "auto"
                      ? "bg-blue-100 text-blue-700"
                      : "bg-green-100 text-green-700"
                  }`}
                >
                  {entry.entry_type === "auto" ? "timer" : "manual"}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-semibold text-foreground">
                    {formatMinutes(entry.minutes)}
                  </span>
                  {entry.description && (
                    <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                      {entry.description}
                    </p>
                  )}
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {formatRelative(entry.created_at)}
                  </p>
                </div>
              </div>
              <button
                onClick={() => deleteEntry.mutate(entry.id)}
                className="hidden group-hover:flex text-muted-foreground hover:text-destructive p-0.5 ml-2 shrink-0"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
