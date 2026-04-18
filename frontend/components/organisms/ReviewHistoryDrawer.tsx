"use client";

import { X, ArrowRight } from "lucide-react";
import { useReviewHistory } from "@/hooks/useKB";
import { StatusBadge } from "@/components/molecules/StatusBadge";
import { Spinner } from "@/components/atoms/Spinner";
import { formatDate } from "@/lib/utils";

interface ReviewHistoryDrawerProps {
  articleId: string;
  open: boolean;
  onClose: () => void;
}

export function ReviewHistoryDrawer({
  articleId,
  open,
  onClose,
}: ReviewHistoryDrawerProps) {
  const { data, isLoading } = useReviewHistory(articleId);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/40" onClick={onClose} />
      <aside className="w-full max-w-md bg-card border-l border-border shadow-xl flex flex-col">
        <header className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-base font-semibold">Historial de revisión</h2>
          <button
            type="button"
            onClick={onClose}
            className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        {isLoading && (
          <div className="flex justify-center py-12">
            <Spinner size="md" />
          </div>
        )}

        {!isLoading && data && (
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
            <div className="grid grid-cols-5 gap-2">
              <SummaryTile label="Enviados" value={data.summary.submitted} />
              <SummaryTile label="Aprobados" value={data.summary.approved} />
              <SummaryTile label="Rechazados" value={data.summary.rejected} />
              <SummaryTile label="Publicados" value={data.summary.published} />
              <SummaryTile label="Devueltos" value={data.summary.returned_to_draft} />
            </div>

            {data.events.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No hay eventos de revisión todavía.
              </p>
            ) : (
              <ol className="flex flex-col gap-3">
                {data.events.map((e) => (
                  <li
                    key={e.id}
                    className="rounded-md border border-border bg-background p-3 flex flex-col gap-1.5"
                  >
                    <div className="flex items-center gap-1.5 text-xs">
                      <StatusBadge status={e.from_status} />
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      <StatusBadge status={e.to_status} />
                    </div>
                    {e.comment && (
                      <p className="text-sm text-foreground">{e.comment}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {formatDate(e.created_at)}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}

function SummaryTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-muted/50 p-2 text-center">
      <div className="text-lg font-semibold text-foreground">{value}</div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wide">
        {label}
      </div>
    </div>
  );
}
