"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { Spinner } from "@/components/atoms/Spinner";

interface Props {
  caseNumber: string;
  open: boolean;
  onClose: () => void;
  /**
   * Submit handler — receives the reason (and optional re-classification
   * fields, deferred to a later UI iteration in sub-spec 02).
   * Should throw on error so the modal can display the message.
   */
  onSubmit: (payload: { reason: string }) => Promise<void>;
}

export function PromoteEventModal({ caseNumber, open, onClose, onSubmit }: Props) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  async function handleSubmit() {
    if (!reason.trim()) {
      setError("La razón es requerida");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await onSubmit({ reason: reason.trim() });
      setReason("");
      onClose();
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Error al promover el evento. Inténtalo de nuevo.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  function handleCancel() {
    if (submitting) return;
    setReason("");
    setError("");
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-card rounded-lg border border-border p-6 w-full max-w-md shadow-xl flex flex-col gap-4">
        <h2 className="text-base font-semibold">Promover evento a incidencia</h2>
        <p className="text-sm text-muted-foreground">
          Estás promoviendo{" "}
          <span className="font-mono font-medium text-foreground">{caseNumber}</span>{" "}
          a una incidencia. Se asignará un nuevo número{" "}
          <span className="font-mono">INC-</span> y el caso pasará a estado{" "}
          <em>triage</em>.
        </p>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-foreground">
            Razón de promoción <span className="text-red-500">*</span>
          </span>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Ej: patrón de fuerza bruta seguido de login exitoso a las 3am"
            rows={4}
            disabled={submitting}
            className="flex w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none disabled:opacity-60"
          />
        </label>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={handleCancel} disabled={submitting}>
            Cancelar
          </Button>
          <Button onClick={handleSubmit} disabled={submitting || !reason.trim()}>
            {submitting ? <Spinner size="sm" /> : null}
            Promover
          </Button>
        </div>
      </div>
    </div>
  );
}
