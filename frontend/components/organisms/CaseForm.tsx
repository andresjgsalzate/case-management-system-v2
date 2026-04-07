"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import { FormField } from "@/components/molecules/FormField";
import { useCreateCase, useCasePriorities, useApplications } from "@/hooks/useCases";

export function CaseForm() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priorityId, setPriorityId] = useState("");
  const [applicationId, setApplicationId] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const { data: priorities = [] } = useCasePriorities();
  const { data: applications = [] } = useApplications();
  const createCase = useCreateCase();

  function validate() {
    const errs: Record<string, string> = {};
    if (!title.trim()) errs.title = "El título es obligatorio";
    if (!priorityId) errs.priority = "Selecciona una prioridad";
    return errs;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }

    try {
      const created = await createCase.mutateAsync({
        title: title.trim(),
        description: description.trim() || undefined,
        priority_id: priorityId,
        application_id: applicationId || undefined,
      });
      router.push(`/cases/${created.id}`);
    } catch {
      setErrors({ submit: "Error al crear el caso. Inténtalo de nuevo." });
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5 max-w-xl">
      <FormField label="Título" htmlFor="title" error={errors.title} required>
        <Input
          id="title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Describe el problema brevemente…"
          error={!!errors.title}
        />
      </FormField>

      <FormField label="Descripción" htmlFor="description">
        <textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Detalles adicionales, pasos para reproducir…"
          rows={4}
          className="flex w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
        />
      </FormField>

      <div className="grid grid-cols-2 gap-4">
        <FormField label="Prioridad" htmlFor="priority" error={errors.priority} required>
          <select
            id="priority"
            value={priorityId}
            onChange={(e) => setPriorityId(e.target.value)}
            className="flex h-9 w-full rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">Seleccionar…</option>
            {priorities.map((p: { id: string; name: string }) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </FormField>

        <FormField label="Aplicación" htmlFor="application">
          <select
            id="application"
            value={applicationId}
            onChange={(e) => setApplicationId(e.target.value)}
            className="flex h-9 w-full rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">Ninguna</option>
            {applications.map((a: { id: string; name: string }) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </FormField>
      </div>

      {errors.submit && (
        <p className="text-sm text-destructive">{errors.submit}</p>
      )}

      <div className="flex gap-3">
        <Button type="submit" loading={createCase.isPending}>
          Crear caso
        </Button>
        <Button type="button" variant="outline" onClick={() => router.back()}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
