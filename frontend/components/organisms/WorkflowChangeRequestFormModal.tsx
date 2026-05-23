"use client";

import { FormEvent, useState } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import { FormField } from "@/components/molecules/FormField";
import { useCreateWCR } from "@/hooks/useWorkflowChangeRequests";
import type { ProposedChangeType } from "@/lib/types";

const CHANGE_TYPES: { value: ProposedChangeType; label: string }[] = [
  { value: "add_step", label: "Agregar paso" },
  { value: "remove_step", label: "Eliminar paso" },
  { value: "modify_step", label: "Modificar paso" },
  { value: "new_workflow", label: "Nuevo workflow" },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export function WorkflowChangeRequestFormModal({ open, onClose }: Props) {
  const create = useCreateWCR();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [changeType, setChangeType] = useState<ProposedChangeType>("modify_step");
  const [details, setDetails] = useState("");
  const [workflowId, setWorkflowId] = useState("");
  const [error, setError] = useState("");

  function reset() {
    setTitle("");
    setDescription("");
    setChangeType("modify_step");
    setDetails("");
    setWorkflowId("");
    setError("");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    try {
      await create.mutateAsync({
        title,
        description,
        workflow_id: workflowId || null,
        proposed_change: {
          type: changeType,
          details,
        },
      });
      reset();
      onClose();
    } catch (err: unknown) {
      const apiErr = err as {
        response?: { data?: { message?: string } };
        message?: string;
      };
      setError(
        apiErr.response?.data?.message ??
          apiErr.message ??
          "No se pudo crear la solicitud."
      );
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg overflow-auto rounded-lg bg-card shadow-xl">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-base font-semibold">
            Nueva solicitud de cambio
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-4 text-sm">
          <FormField label="Título" htmlFor="wcr-title">
            <Input
              id="wcr-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Agregar retry al paso de Slack"
              required
              maxLength={200}
            />
          </FormField>

          <FormField label="Descripción" htmlFor="wcr-description">
            <textarea
              id="wcr-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Contexto, motivo, impacto esperado…"
              required
              rows={4}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </FormField>

          <FormField label="Tipo de cambio" htmlFor="wcr-type">
            <select
              id="wcr-type"
              value={changeType}
              onChange={(e) => setChangeType(e.target.value as ProposedChangeType)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {CHANGE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Detalle del cambio" htmlFor="wcr-details">
            <textarea
              id="wcr-details"
              value={details}
              onChange={(e) => setDetails(e.target.value)}
              placeholder="Especificación técnica del cambio propuesto…"
              required
              rows={3}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm font-mono"
            />
          </FormField>

          <FormField
            label="Workflow ID (opcional)"
            htmlFor="wcr-workflow-id"
          >
            <Input
              id="wcr-workflow-id"
              value={workflowId}
              onChange={(e) => setWorkflowId(e.target.value)}
              placeholder="UUID del workflow existente"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Déjalo en blanco si propones un workflow nuevo.
            </p>
          </FormField>

          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" loading={create.isPending}>
              Crear solicitud
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
