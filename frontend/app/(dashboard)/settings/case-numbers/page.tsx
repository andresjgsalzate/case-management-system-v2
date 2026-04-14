"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Hash, Plus, Trash2, AlertCircle, CheckCircle2, Clock } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import type { ApiResponse } from "@/lib/types";

// ── Types ────────────────────────────────────────────────────────────────────

interface NumberRange {
  id: string;
  prefix: string;
  range_start: number;
  range_end: number;
  current_number: number;
  total: number;
  used: number;
  remaining: number;
  status: "active" | "pending" | "exhausted";
  preview_first: string;
  preview_last: string;
  created_at: string;
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

function useRanges() {
  return useQuery({
    queryKey: ["case-number-ranges"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<NumberRange[]>>(
        "/case-number-ranges"
      );
      return data.data ?? [];
    },
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number) {
  return String(n).padStart(6, "0");
}

function previewNumber(prefix: string, n: number) {
  const p = prefix.toUpperCase() || "REQ";
  return `${p}${fmt(n)}`;
}

function StatusBadge({ status }: { status: NumberRange["status"] }) {
  if (status === "active") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
        <CheckCircle2 className="h-3 w-3" />
        Activo
      </span>
    );
  }
  if (status === "pending") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
        <Clock className="h-3 w-3" />
        Pendiente
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground">
      <AlertCircle className="h-3 w-3" />
      Agotado
    </span>
  );
}

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ used, total }: { used: number; total: number }) {
  const pct = total === 0 ? 0 : Math.round((used / total) * 100);
  const color =
    pct >= 90
      ? "bg-red-500"
      : pct >= 70
      ? "bg-amber-500"
      : "bg-primary";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-muted-foreground tabular-nums w-10 text-right">{pct}%</span>
    </div>
  );
}

// ── Create form ───────────────────────────────────────────────────────────────

function CreateRangeForm({
  ranges,
  onSave,
  onCancel,
  isPending,
  error,
}: {
  ranges: NumberRange[];
  onSave: (body: { prefix: string; range_end: number }) => void;
  onCancel: () => void;
  isPending: boolean;
  error: string;
}) {
  const [prefix, setPrefix] = useState("");
  const [rangeEnd, setRangeEnd] = useState<number | "">(200000);

  // If prefix already exists, auto-compute range_start
  const existingForPrefix = ranges
    .filter((r) => r.prefix === prefix.toUpperCase())
    .sort((a, b) => b.range_end - a.range_end);

  const maxEnd = existingForPrefix[0]?.range_end ?? 0;
  const rangeStart = maxEnd + 1;
  const isNewPrefix = existingForPrefix.length === 0;

  const endNum = Number(rangeEnd) || 0;
  const valid =
    prefix.length >= 2 &&
    prefix.length <= 4 &&
    /^[A-Za-z]+$/.test(prefix) &&
    endNum >= rangeStart;

  return (
    <div className="rounded-lg border border-primary/30 bg-card p-5 flex flex-col gap-4">
      <p className="text-sm font-semibold text-foreground">Nuevo rango de numeración</p>

      {/* Live preview */}
      <div className="flex items-center gap-3 p-3 rounded-md bg-muted/50 font-mono text-sm">
        <Hash className="h-4 w-4 text-muted-foreground shrink-0" />
        <span className="text-muted-foreground">
          {previewNumber(prefix || "REQ", rangeStart)}
        </span>
        <span className="text-muted-foreground mx-1">→</span>
        <span className="font-bold text-foreground">
          {previewNumber(prefix || "REQ", endNum || rangeStart)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Prefix */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            Prefijo <span className="font-normal">(2–4 letras)</span>
          </label>
          <input
            className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary uppercase font-mono"
            value={prefix}
            maxLength={4}
            placeholder="REQ"
            onChange={(e) =>
              setPrefix(e.target.value.toUpperCase().replace(/[^A-Z]/g, ""))
            }
          />
          <p className="text-xs text-muted-foreground">Ej: REQ, INC, SOL, TICK</p>
        </div>

        {/* Range start — readonly, auto-computed */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            Desde (automático)
          </label>
          <input
            readOnly
            className="px-3 py-2 text-sm rounded-md border border-border bg-muted text-muted-foreground font-mono cursor-not-allowed"
            value={fmt(rangeStart)}
          />
          <p className="text-xs text-muted-foreground">
            {isNewPrefix
              ? "Nuevo prefijo — comienza en 000001"
              : `Continuación desde ${previewNumber(prefix, maxEnd)}`}
          </p>
        </div>

        {/* Range end */}
        <div className="col-span-2 flex flex-col gap-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            Hasta (número final del rango)
          </label>
          <input
            type="number"
            min={rangeStart}
            className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary w-48 font-mono"
            value={rangeEnd}
            onChange={(e) => setRangeEnd(e.target.value === "" ? "" : Number(e.target.value))}
          />
          {endNum > 0 && endNum >= rangeStart && (
            <p className="text-xs text-muted-foreground">
              Capacidad: <span className="font-semibold text-foreground">{(endNum - rangeStart + 1).toLocaleString()}</span> números
              ({previewNumber(prefix || "REQ", rangeStart)} — {previewNumber(prefix || "REQ", endNum)})
            </p>
          )}
          {endNum > 0 && endNum < rangeStart && (
            <p className="text-xs text-destructive">
              Debe ser mayor o igual a {rangeStart.toLocaleString()}
            </p>
          )}
        </div>
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      <div className="flex gap-2 justify-end border-t border-border pt-3">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Cancelar
        </button>
        <button
          type="button"
          disabled={!valid || isPending}
          onClick={() => onSave({ prefix: prefix.toUpperCase(), range_end: endNum })}
          className="flex items-center gap-2 px-4 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Plus className="h-4 w-4" />
          {isPending ? "Creando…" : "Crear rango"}
        </button>
      </div>
    </div>
  );
}

// ── Range card ────────────────────────────────────────────────────────────────

function RangeCard({
  rng,
  onDelete,
}: {
  rng: NumberRange;
  onDelete: (id: string) => void;
}) {
  const canDelete = rng.current_number < rng.range_start;
  return (
    <div className="rounded-lg border border-border bg-card p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
            <Hash className="h-4 w-4 text-primary" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold text-foreground">{rng.prefix}</span>
              <StatusBadge status={rng.status} />
            </div>
            <p className="text-xs text-muted-foreground font-mono mt-0.5">
              {rng.preview_first} → {rng.preview_last}
            </p>
          </div>
        </div>

        {canDelete && (
          <button
            type="button"
            title="Eliminar rango"
            onClick={() => onDelete(rng.id)}
            className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/5 transition-colors"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>

      <ProgressBar used={rng.used} total={rng.total} />

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-md bg-muted/50 p-2">
          <p className="text-xs text-muted-foreground">Capacidad</p>
          <p className="text-sm font-semibold text-foreground tabular-nums">{rng.total.toLocaleString()}</p>
        </div>
        <div className="rounded-md bg-muted/50 p-2">
          <p className="text-xs text-muted-foreground">Usados</p>
          <p className="text-sm font-semibold text-foreground tabular-nums">{rng.used.toLocaleString()}</p>
        </div>
        <div className="rounded-md bg-muted/50 p-2">
          <p className="text-xs text-muted-foreground">Disponibles</p>
          <p className="text-sm font-semibold text-foreground tabular-nums">{rng.remaining.toLocaleString()}</p>
        </div>
      </div>

      {rng.status === "active" && rng.remaining <= rng.total * 0.1 && (
        <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-md px-3 py-2">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          Quedan pocos números. Considera crear un rango de continuación.
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CaseNumbersSettingsPage() {
  const confirm = useConfirm();
  const qc = useQueryClient();
  const { data: ranges = [], isLoading } = useRanges();
  const [showForm, setShowForm] = useState(false);
  const [formError, setFormError] = useState("");

  const createMutation = useMutation({
    mutationFn: (body: { prefix: string; range_end: number }) =>
      apiClient.post("/case-number-ranges", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case-number-ranges"] });
      setShowForm(false);
      setFormError("");
    },
    onError: (e: unknown) => {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setFormError(msg ?? "Error al crear el rango");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/case-number-ranges/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case-number-ranges"] }),
    onError: (e: unknown) => {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      alert(msg ?? "No se pudo eliminar el rango");
    },
  });

  // Group ranges by prefix
  const byPrefix = ranges.reduce<Record<string, NumberRange[]>>((acc, r) => {
    acc[r.prefix] = acc[r.prefix] ?? [];
    acc[r.prefix].push(r);
    return acc;
  }, {});

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Numeración de Casos</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Define rangos de numeración por prefijo. Los rangos del mismo prefijo deben ser consecutivos.
          </p>
        </div>
        {!showForm && (
          <button
            type="button"
            onClick={() => { setShowForm(true); setFormError(""); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shrink-0"
          >
            <Plus className="h-4 w-4" />
            Nuevo rango
          </button>
        )}
      </div>

      {/* Create form */}
      {showForm && (
        <CreateRangeForm
          ranges={ranges}
          onSave={(body) => createMutation.mutate(body)}
          onCancel={() => { setShowForm(false); setFormError(""); }}
          isPending={createMutation.isPending}
          error={formError}
        />
      )}

      {/* Ranges grouped by prefix */}
      {Object.keys(byPrefix).length === 0 && !showForm && (
        <div className="rounded-lg border border-dashed border-border bg-card p-8 flex flex-col items-center gap-3 text-center">
          <Hash className="h-8 w-8 text-muted-foreground/50" />
          <div>
            <p className="text-sm font-medium text-foreground">Sin rangos configurados</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Crea un rango para que los agentes puedan crear casos.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="mt-1 flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md border border-dashed border-border hover:border-primary/40 text-muted-foreground hover:text-foreground transition-colors"
          >
            <Plus className="h-4 w-4" />
            Crear primer rango
          </button>
        </div>
      )}

      {Object.entries(byPrefix).map(([prefix, prefixRanges]) => (
        <div key={prefix} className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Prefijo
            </span>
            <span className="font-mono font-bold text-foreground">{prefix}</span>
            <span className="text-xs text-muted-foreground">
              — {prefixRanges.length} rango{prefixRanges.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="flex flex-col gap-2">
            {prefixRanges.map((rng) => (
              <RangeCard
                key={rng.id}
                rng={rng}
                onDelete={async (id) => {
                  const ok = await confirm({
                    title: "¿Eliminar rango?",
                    description: `Se eliminará el rango ${rng.preview_first} → ${rng.preview_last}. Esta acción no se puede deshacer.`,
                    confirmLabel: "Eliminar",
                  });
                  if (ok) deleteMutation.mutate(id);
                }}
              />
            ))}
          </div>
        </div>
      ))}

      {/* Info note */}
      <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-4">
        <p className="text-sm text-amber-800 dark:text-amber-200 font-medium">Cómo funciona</p>
        <ul className="text-xs text-amber-700 dark:text-amber-300 mt-1 space-y-1 list-disc list-inside">
          <li>El rango <strong>Activo</strong> es el que se usa para los próximos casos.</li>
          <li>Los rangos <strong>Pendientes</strong> se activarán cuando el activo se agote.</li>
          <li>Puedes tener varios prefijos (REQ, INC, SOL…) con sus propios rangos independientes.</li>
          <li>Al agregar un segundo rango del mismo prefijo, el número inicial se calcula automáticamente para garantizar consecutividad.</li>
          <li>Solo se pueden eliminar rangos que aún no han generado ningún número.</li>
        </ul>
      </div>
    </div>
  );
}
