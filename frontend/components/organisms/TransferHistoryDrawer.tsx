"use client";

import { X, ArrowUpRight, ArrowDown, ArrowRight } from "lucide-react";
import { useCaseTransfers } from "@/hooks/useTransferCase";
import { Spinner } from "@/components/atoms/Spinner";
import { formatDate } from "@/lib/utils";
import type { CaseTransferType } from "@/lib/types";

interface TransferHistoryDrawerProps {
  caseId: string;
  open: boolean;
  onClose: () => void;
}

const ICONS: Record<CaseTransferType, React.ComponentType<{ className?: string }>> = {
  escalate: ArrowUpRight,
  "de-escalate": ArrowDown,
  reassign: ArrowRight,
};

const LABELS: Record<CaseTransferType, string> = {
  escalate: "Escalado",
  "de-escalate": "De-escalado",
  reassign: "Reasignado",
};

export function TransferHistoryDrawer({ caseId, open, onClose }: TransferHistoryDrawerProps) {
  const { data: transfers = [], isLoading } = useCaseTransfers(caseId);
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md h-full bg-card border-l border-border flex flex-col"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold">Historial de transferencias</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
          {isLoading && <Spinner size="sm" />}
          {!isLoading && transfers.length === 0 && (
            <p className="text-xs text-muted-foreground">Sin transferencias registradas.</p>
          )}
          {transfers.map((t) => {
            const Icon = ICONS[t.transfer_type];
            return (
              <div key={t.id} className="rounded-md border border-border p-3 flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{LABELS[t.transfer_type]}</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {formatDate(t.created_at)}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Nivel {t.from_level} → Nivel {t.to_level}
                </p>
                <p className="text-xs text-foreground whitespace-pre-wrap">{t.reason}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
