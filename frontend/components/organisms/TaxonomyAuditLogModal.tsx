"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { useTaxonomyAuditLog } from "@/hooks/useSecurityTaxonomies";
import type { TaxonomyChangeType } from "@/lib/types";
import { cn } from "@/lib/utils";

const CHANGE_TYPE_LABEL: Record<TaxonomyChangeType, string> = {
  created: "Creado",
  updated: "Actualizado",
  soft_deleted: "Eliminado",
  activated: "Activado",
  forked: "Forkeado",
  refreshed_from_global: "Re-syncado desde global",
};

const CHANGE_TYPE_COLOR: Record<TaxonomyChangeType, string> = {
  created: "text-green-700 dark:text-green-400",
  updated: "text-blue-700 dark:text-blue-400",
  soft_deleted: "text-red-700 dark:text-red-400",
  activated: "text-green-700 dark:text-green-400",
  forked: "text-purple-700 dark:text-purple-400",
  refreshed_from_global: "text-amber-700 dark:text-amber-400",
};

interface TaxonomyAuditLogModalProps {
  taxonomyId: string | null;
  taxonomyName?: string;
  isOpen: boolean;
  onClose: () => void;
}

export function TaxonomyAuditLogModal({
  taxonomyId,
  taxonomyName,
  isOpen,
  onClose,
}: TaxonomyAuditLogModalProps) {
  const [filter, setFilter] = useState<TaxonomyChangeType | "">("");
  const { data: entries, isLoading, error } = useTaxonomyAuditLog(
    isOpen ? taxonomyId : null,
    filter || undefined,
  );

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="audit-log-title"
    >
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col rounded-lg bg-background shadow-xl">
        <header className="flex items-start justify-between border-b p-4">
          <div>
            <h2 id="audit-log-title" className="text-lg font-semibold">
              Histórico de cambios
            </h2>
            {taxonomyName ? (
              <p className="text-sm text-muted-foreground">{taxonomyName}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="border-b p-3">
          <label className="text-xs font-medium text-muted-foreground">
            Filtrar por tipo
          </label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as TaxonomyChangeType | "")}
            className="mt-1 block w-full max-w-xs rounded border bg-background px-2 py-1 text-sm"
          >
            <option value="">Todos</option>
            {Object.entries(CHANGE_TYPE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Cargando...</p>
          ) : error ? (
            <p className="text-sm text-red-600">
              Error al cargar el histórico: {(error as Error).message}
            </p>
          ) : !entries || entries.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No hay cambios registrados con este filtro.
            </p>
          ) : (
            <ol className="space-y-3">
              {entries.map((entry) => (
                <li
                  key={entry.id}
                  className="rounded border bg-card p-3 text-sm"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span
                      className={cn(
                        "font-semibold",
                        CHANGE_TYPE_COLOR[entry.change_type],
                      )}
                    >
                      {CHANGE_TYPE_LABEL[entry.change_type] ?? entry.change_type}
                    </span>
                    <time className="text-xs text-muted-foreground">
                      {new Date(entry.changed_at).toLocaleString()}
                    </time>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    por <span className="font-mono">{entry.changed_by}</span>
                  </p>
                  {entry.reason ? (
                    <p className="mt-1 text-xs italic">Motivo: {entry.reason}</p>
                  ) : null}
                  {renderFieldChanges(entry.field_changes)}
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}

function renderFieldChanges(
  changes: Record<string, { from: unknown; to: unknown } | unknown>,
): React.ReactNode {
  const entries = Object.entries(changes);
  if (entries.length === 0) return null;

  return (
    <dl className="mt-2 space-y-0.5 text-xs">
      {entries.map(([field, change]) => {
        // Heuristic: real diff entries have {from, to}; otherwise dump JSON
        if (
          change && typeof change === "object" &&
          "from" in (change as Record<string, unknown>) &&
          "to" in (change as Record<string, unknown>)
        ) {
          const diff = change as { from: unknown; to: unknown };
          return (
            <div key={field} className="flex items-baseline gap-2">
              <dt className="font-medium">{field}:</dt>
              <dd className="text-muted-foreground">
                <code className="rounded bg-muted px-1">{stringify(diff.from)}</code>
                {" → "}
                <code className="rounded bg-muted px-1">{stringify(diff.to)}</code>
              </dd>
            </div>
          );
        }
        return (
          <div key={field} className="flex items-baseline gap-2">
            <dt className="font-medium">{field}:</dt>
            <dd className="text-muted-foreground font-mono">
              {stringify(change)}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

function stringify(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
