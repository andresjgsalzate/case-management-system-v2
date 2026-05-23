"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import { FormField } from "@/components/molecules/FormField";
import { useHasPermission } from "@/hooks/useHasPermission";
import {
  useImplementWCR,
  useUpdateWCRStatus,
} from "@/hooks/useWorkflowChangeRequests";
import type { WCRStatus, WorkflowChangeRequest } from "@/lib/types";

interface Props {
  wcr: WorkflowChangeRequest | null;
  onClose: () => void;
}

export function WorkflowChangeRequestReviewModal({ wcr, onClose }: Props) {
  const canReview = useHasPermission("workflow_change_requests", "review");
  const transition = useUpdateWCRStatus();
  const implement = useImplementWCR();

  const [reviewNotes, setReviewNotes] = useState("");
  const [implWorkflowId, setImplWorkflowId] = useState("");
  const [implWorkflowUrl, setImplWorkflowUrl] = useState("");
  const [error, setError] = useState("");

  // Reset local state every time a different WCR opens.
  useEffect(() => {
    if (wcr) {
      setReviewNotes(wcr.review_notes ?? "");
      setImplWorkflowId("");
      setImplWorkflowUrl("");
      setError("");
    }
  }, [wcr?.id]);

  if (!wcr) return null;

  const isTerminal = wcr.status === "rejected" || wcr.status === "implemented";
  const allowedTransitions: WCRStatus[] = (() => {
    if (!canReview || isTerminal) return [];
    switch (wcr.status) {
      case "pending":
        return ["in_review", "approved", "rejected"];
      case "in_review":
        return ["approved", "rejected"];
      case "approved":
        return ["rejected"]; // can still reject before implementing
      default:
        return [];
    }
  })();

  async function handleTransition(target: WCRStatus) {
    setError("");
    try {
      await transition.mutateAsync({
        id: wcr!.id,
        body: {
          status: target as "in_review" | "approved" | "rejected",
          review_notes: reviewNotes || null,
        },
      });
      onClose();
    } catch (err: unknown) {
      const apiErr = err as {
        response?: { data?: { message?: string } };
        message?: string;
      };
      setError(apiErr.response?.data?.message ?? apiErr.message ?? "Error");
    }
  }

  async function handleImplement() {
    setError("");
    if (!implWorkflowId || !implWorkflowUrl) {
      setError("Se requiere workflow ID + URL para marcar implementado.");
      return;
    }
    try {
      await implement.mutateAsync({
        id: wcr!.id,
        body: {
          workflow_id: implWorkflowId,
          workflow_url: implWorkflowUrl,
        },
      });
      onClose();
    } catch (err: unknown) {
      const apiErr = err as {
        response?: { data?: { message?: string } };
        message?: string;
      };
      setError(apiErr.response?.data?.message ?? apiErr.message ?? "Error");
    }
  }

  const busy = transition.isPending || implement.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-lg bg-card shadow-xl">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-base font-semibold">{wcr.title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="space-y-4 p-4 text-sm">
          <section className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <dt className="font-medium text-muted-foreground">Estado actual</dt>
            <dd>{wcr.status}</dd>
            <dt className="font-medium text-muted-foreground">Tipo</dt>
            <dd className="font-mono">{wcr.proposed_change.type}</dd>
            <dt className="font-medium text-muted-foreground">Solicitado por</dt>
            <dd className="font-mono break-all">{wcr.requested_by}</dd>
            <dt className="font-medium text-muted-foreground">Solicitado en</dt>
            <dd>
              {wcr.requested_at
                ? new Date(wcr.requested_at).toLocaleString()
                : "—"}
            </dd>
            {wcr.workflow_id && (
              <>
                <dt className="font-medium text-muted-foreground">
                  Workflow asociado
                </dt>
                <dd className="font-mono break-all">{wcr.workflow_id}</dd>
              </>
            )}
          </section>

          <section>
            <h3 className="text-sm font-semibold mb-1">Descripción</h3>
            <p className="text-sm whitespace-pre-wrap">{wcr.description}</p>
          </section>

          <section>
            <h3 className="text-sm font-semibold mb-1">Cambio propuesto</h3>
            <pre className="overflow-auto rounded bg-muted/40 p-3 text-xs">
              {JSON.stringify(wcr.proposed_change, null, 2)}
            </pre>
          </section>

          {wcr.review_notes && (
            <section>
              <h3 className="text-sm font-semibold mb-1">Notas de revisión</h3>
              <p className="text-sm whitespace-pre-wrap rounded bg-muted/40 p-3">
                {wcr.review_notes}
              </p>
            </section>
          )}

          {wcr.implemented_in_workflow_url && (
            <section className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs dark:border-emerald-900 dark:bg-emerald-950/30">
              <p className="font-semibold text-emerald-900 dark:text-emerald-200">
                Implementado en
              </p>
              <code className="break-all text-emerald-900 dark:text-emerald-200">
                {wcr.implemented_in_workflow_url}
              </code>
            </section>
          )}

          {canReview && !isTerminal && (
            <section className="border-t pt-4 space-y-3">
              <FormField label="Notas de revisión" htmlFor="wcr-notes">
                <textarea
                  id="wcr-notes"
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  rows={3}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="Comentarios para el solicitante…"
                />
              </FormField>

              <div className="flex flex-wrap gap-2">
                {allowedTransitions.includes("in_review") && (
                  <Button
                    variant="outline"
                    onClick={() => handleTransition("in_review")}
                    loading={busy}
                  >
                    Tomar revisión
                  </Button>
                )}
                {allowedTransitions.includes("approved") && (
                  <Button
                    onClick={() => handleTransition("approved")}
                    loading={busy}
                  >
                    Aprobar
                  </Button>
                )}
                {allowedTransitions.includes("rejected") && (
                  <Button
                    variant="outline"
                    onClick={() => handleTransition("rejected")}
                    loading={busy}
                  >
                    Rechazar
                  </Button>
                )}
              </div>

              {wcr.status === "approved" && (
                <div className="rounded-md border border-border p-3 space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Marcar implementado
                  </p>
                  <FormField label="Workflow ID" htmlFor="impl-id">
                    <Input
                      id="impl-id"
                      value={implWorkflowId}
                      onChange={(e) => setImplWorkflowId(e.target.value)}
                      placeholder="UUID del workflow donde se aplicó"
                    />
                  </FormField>
                  <FormField label="Workflow URL" htmlFor="impl-url">
                    <Input
                      id="impl-url"
                      value={implWorkflowUrl}
                      onChange={(e) => setImplWorkflowUrl(e.target.value)}
                      placeholder="https://cms.local/webhook/…"
                    />
                  </FormField>
                  <Button onClick={handleImplement} loading={busy}>
                    Marcar implementado
                  </Button>
                </div>
              )}
            </section>
          )}

          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
