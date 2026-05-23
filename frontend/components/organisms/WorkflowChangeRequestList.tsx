"use client";

import { useState } from "react";
import { GitPullRequest } from "lucide-react";

import { useWCRs } from "@/hooks/useWorkflowChangeRequests";
import type { WCRStatus, WorkflowChangeRequest } from "@/lib/types";

const STATUS_FILTERS: { value: WCRStatus | "all"; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "pending", label: "Pendientes" },
  { value: "in_review", label: "En revisión" },
  { value: "approved", label: "Aprobados" },
  { value: "rejected", label: "Rechazados" },
  { value: "implemented", label: "Implementados" },
];

const STATUS_STYLES: Record<WCRStatus, string> = {
  pending: "bg-amber-100 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200",
  in_review: "bg-blue-100 text-blue-900 dark:bg-blue-950/40 dark:text-blue-200",
  approved: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200",
  rejected: "bg-rose-100 text-rose-900 dark:bg-rose-950/40 dark:text-rose-200",
  implemented: "bg-slate-200 text-slate-900 dark:bg-slate-700/40 dark:text-slate-200",
};

interface Props {
  onOpenReview: (wcr: WorkflowChangeRequest) => void;
}

export function WorkflowChangeRequestList({ onOpenReview }: Props) {
  const [activeFilter, setActiveFilter] = useState<WCRStatus | "all">("all");
  const { data, isLoading, error } = useWCRs(
    activeFilter === "all" ? {} : { status: activeFilter }
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1.5">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setActiveFilter(f.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              activeFilter === f.value
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:text-foreground"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        {isLoading ? (
          <p className="p-4 text-sm text-muted-foreground">Cargando solicitudes…</p>
        ) : error ? (
          <p className="p-4 text-sm text-destructive">Error al cargar solicitudes.</p>
        ) : !data || data.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 p-8 text-center">
            <GitPullRequest className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Sin solicitudes en este filtro.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left">
              <tr>
                <th className="px-3 py-2 font-medium">Título</th>
                <th className="px-3 py-2 font-medium">Tipo</th>
                <th className="px-3 py-2 font-medium">Estado</th>
                <th className="px-3 py-2 font-medium">Solicitado</th>
                <th className="px-3 py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {data.map((wcr) => (
                <tr
                  key={wcr.id}
                  className="border-b last:border-0 hover:bg-muted/30 cursor-pointer"
                  onClick={() => onOpenReview(wcr)}
                >
                  <td className="px-3 py-2">
                    <p className="font-medium">{wcr.title}</p>
                    <p className="text-xs text-muted-foreground line-clamp-1">
                      {wcr.description}
                    </p>
                  </td>
                  <td className="px-3 py-2 text-xs font-mono text-muted-foreground">
                    {wcr.proposed_change.type}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[wcr.status]}`}
                    >
                      {wcr.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {wcr.requested_at
                      ? new Date(wcr.requested_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      className="text-xs text-primary hover:underline"
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenReview(wcr);
                      }}
                    >
                      Ver detalle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
