"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { useDecideApproval } from "@/hooks/useApprovalRequests";
import type { ApprovalInboxRow } from "@/lib/types";

interface Props {
  isOpen: boolean;
  approval: ApprovalInboxRow | null;
  decision: "approved" | "rejected";
  onClose: () => void;
  onDecided?: () => void;
}

export function ApprovalDecideModal({
  isOpen, approval, decision, onClose, onDecided,
}: Props) {
  const decide = useDecideApproval();
  const [reason, setReason] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen || !approval) return null;

  function close() {
    setReason("");
    setErrorMsg(null);
    onClose();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg(null);
    if (decision === "rejected" && !reason.trim()) {
      setErrorMsg("Razón obligatoria para rechazar.");
      return;
    }
    if (!approval) return;
    try {
      await decide.mutateAsync({
        id: approval.id,
        payload: { decision, reason: reason.trim() || null },
      });
      onDecided?.();
      close();
    } catch (err) {
      setErrorMsg(
        err instanceof Error ? err.message : "Error al guardar la decisión",
      );
    }
  }

  const verb = decision === "approved" ? "Aprobar" : "Rechazar";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-lg bg-card shadow-xl">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-base font-semibold">{verb} approval</h2>
          <button
            type="button"
            onClick={close}
            className="rounded p-1 hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <form onSubmit={handleSubmit} className="space-y-4 p-4">
          <div className="rounded bg-muted/30 p-3 text-sm">
            <p className="font-medium">{approval.requested_action}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {approval.action_category} · case {approval.case_id.slice(0, 8)}
            </p>
          </div>

          <label className="block text-sm">
            <span className="mb-1 block font-medium">
              Razón {decision === "rejected" ? "*" : "(opcional)"}
            </span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={4}
              placeholder={
                decision === "rejected"
                  ? "Ej: La IP origen pertenece a un usuario legítimo"
                  : "Notas opcionales para el audit log"
              }
              className="w-full rounded border px-2 py-1 text-sm"
            />
          </label>

          {errorMsg ? (
            <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
              {errorMsg}
            </p>
          ) : null}

          <footer className="flex justify-end gap-2 border-t pt-3">
            <button
              type="button"
              onClick={close}
              className="rounded border px-3 py-1.5 text-sm hover:bg-muted"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={decide.isPending}
              className={`rounded px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 ${
                decision === "approved"
                  ? "bg-green-600 hover:bg-green-700"
                  : "bg-red-600 hover:bg-red-700"
              }`}
            >
              {decide.isPending ? "Guardando…" : verb}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
