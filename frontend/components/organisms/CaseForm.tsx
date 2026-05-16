"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import { FormField } from "@/components/molecules/FormField";
import { useCreateCase, useCasePriorities, useApplications } from "@/hooks/useCases";
import {
  useServiceCategories,
  useServiceItems,
  useItemFields,
} from "@/hooks/useServiceCatalog";
import { FieldPreview } from "@/components/organisms/ServiceCatalog/FieldPreview";
import { TaxonomySelector } from "@/components/molecules/TaxonomySelector";
import { useAuthStore } from "@/store/auth.store";
import { hasPermission } from "@/lib/permissions";
import type { CaseType, ServiceCatalogField } from "@/lib/types";

export function CaseForm() {
  const router = useRouter();

  // Per-type creation permissions (sub-spec 01 § 3.6)
  const permissions = useAuthStore((s) => s.user?.permissions);
  const canCreate = {
    request: hasPermission(permissions, "cases", "create:request"),
    incident: hasPermission(permissions, "cases", "create:incident"),
    event: hasPermission(permissions, "cases", "create:event"),
  };
  // Default to first allowed type (preference: request → incident → event)
  const initialType: CaseType = canCreate.request
    ? "request"
    : canCreate.incident
    ? "incident"
    : canCreate.event
    ? "event"
    : "request";
  const [caseType, setCaseType] = useState<CaseType>(initialType);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priorityId, setPriorityId] = useState("");
  const [applicationId, setApplicationId] = useState("");

  // Service catalog
  const [categoryId, setCategoryId] = useState("");
  const [serviceItemId, setServiceItemId] = useState("");
  const [customValues, setCustomValues] = useState<Record<string, string>>({});
  // Sub-spec 02: taxonomy selector for incident/event types
  const [taxonomyId, setTaxonomyId] = useState<string | null>(null);

  const [errors, setErrors] = useState<Record<string, string>>({});

  const { data: priorities = [] } = useCasePriorities();
  const { data: applications = [] } = useApplications();
  const { data: categories = [] } = useServiceCategories();
  const { data: items = [] } = useServiceItems(categoryId || null);
  const { data: fields = [] } = useItemFields(serviceItemId || undefined);
  const createCase = useCreateCase();

  // Apply defaults from selected service item
  const selectedItem = items.find((i) => i.id === serviceItemId);
  useEffect(() => {
    if (selectedItem) {
      if (!priorityId && selectedItem.default_priority_id) {
        setPriorityId(selectedItem.default_priority_id);
      }
    }
    // Reset valores custom cuando cambia el item
    setCustomValues({});
  }, [serviceItemId]); // eslint-disable-line react-hooks/exhaustive-deps

  function setCustomValue(fieldId: string, value: string) {
    setCustomValues((prev) => ({ ...prev, [fieldId]: value }));
  }

  function validate() {
    const errs: Record<string, string> = {};
    if (!categoryId) errs.category = "Selecciona una categoría";
    if (!serviceItemId) errs.serviceItem = "Selecciona el tipo de solicitud";
    if (!title.trim()) errs.title = "El título es obligatorio";
    if (!priorityId) errs.priority = "Selecciona una prioridad";
    // Validate required custom fields
    for (const f of fields) {
      if (f.is_required && !customValues[f.id]) {
        errs[`cv_${f.id}`] = `El campo "${f.label}" es obligatorio`;
      }
    }
    return errs;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }

    try {
      const created = await createCase.mutateAsync({
        case_type: caseType,
        title: title.trim(),
        description: description.trim() || undefined,
        priority_id: priorityId,
        application_id: applicationId || undefined,
        service_item_id: serviceItemId,
        // Sub-spec 02: taxonomy only relevant for incident/event
        taxonomy_id: caseType !== "request" ? (taxonomyId ?? undefined) : undefined,
        custom_values: fields
          .map((f) => ({ field_id: f.id, value: customValues[f.id] ?? null }))
          .filter((v) => v.value !== null && v.value !== ""),
      });
      router.push(`/cases/${created.id}`);
    } catch {
      setErrors({ submit: "Error al crear el caso. Inténtalo de nuevo." });
    }
  }

  // Empty state: si el catálogo no tiene categorías ni items activos
  const activeCategories = categories.filter((c) => c.is_active);
  if (activeCategories.length === 0) {
    return (
      <div className="rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/20 p-5 max-w-xl">
        <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
          No hay servicios disponibles para crear casos
        </p>
        <p className="text-xs text-amber-800 dark:text-amber-300 mt-1">
          Pídele al administrador que cree al menos una categoría con un ítem en el
          {" "}
          <a href="/settings/service-catalog" className="underline">catálogo de servicios</a>.
        </p>
      </div>
    );
  }

  const hasCustomFields = fields.length > 0;

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6 max-w-6xl">
      {/* Tipo de caso (radio): visible solo si el usuario tiene
          permisos para crear más de un tipo. Si solo puede crear uno,
          el radio se oculta y el valor por defecto sigue activo. */}
      {(Number(canCreate.request) + Number(canCreate.incident) + Number(canCreate.event)) > 1 && (
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-foreground">Tipo</label>
          <div className="flex gap-4 flex-wrap">
            {canCreate.request && (
              <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="case_type"
                  value="request"
                  checked={caseType === "request"}
                  onChange={() => setCaseType("request")}
                  className="accent-primary"
                />
                Solicitud
              </label>
            )}
            {canCreate.incident && (
              <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="case_type"
                  value="incident"
                  checked={caseType === "incident"}
                  onChange={() => setCaseType("incident")}
                  className="accent-primary"
                />
                Incidencia
              </label>
            )}
            {canCreate.event && (
              <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="case_type"
                  value="event"
                  checked={caseType === "event"}
                  onChange={() => setCaseType("event")}
                  className="accent-primary"
                />
                Evento
              </label>
            )}
          </div>
        </div>
      )}

      {/* Sub-spec 02: Taxonomía de seguridad — solo para incident y event */}
      {caseType !== "request" && (
        <div className="flex flex-col gap-1 max-w-2xl">
          <label className="text-sm font-medium text-foreground">
            Taxonomía de seguridad
            <span className="ml-1 text-xs font-normal text-muted-foreground">
              (opcional — clasifica el evento/incidente)
            </span>
          </label>
          <TaxonomySelector
            value={taxonomyId}
            onChange={(id) => setTaxonomyId(id)}
            caseTypeFilter={caseType}
            placeholder="— Sin taxonomía —"
          />
        </div>
      )}

      {/* Layout adaptativo:
          - Sin campos custom → 1 columna con ancho moderado.
          - Con campos custom → 2 columnas en lg+, apiladas en sm/md. */}
      <div
        className={
          hasCustomFields
            ? "grid grid-cols-1 lg:grid-cols-2 gap-6 items-start"
            : "max-w-2xl"
        }
      >
        {/* ── Columna izquierda: campos básicos del caso ───────────────────── */}
        <div className="flex flex-col gap-5">
          {/* Service catalog selector */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FormField label="Categoría de servicio" htmlFor="category" error={errors.category} required>
              <select
                id="category"
                value={categoryId}
                onChange={(e) => {
                  setCategoryId(e.target.value);
                  setServiceItemId("");
                }}
                required
                className="flex h-9 w-full rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">Selecciona una categoría…</option>
                {activeCategories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </FormField>

            <FormField label="Tipo de solicitud" htmlFor="service-item" error={errors.serviceItem} required>
              <select
                id="service-item"
                value={serviceItemId}
                onChange={(e) => setServiceItemId(e.target.value)}
                disabled={!categoryId}
                required
                className="flex h-9 w-full rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
              >
                <option value="">
                  {categoryId ? "Selecciona un tipo…" : "Primero elige categoría"}
                </option>
                {items.filter((i) => i.is_active).map((i) => (
                  <option key={i.id} value={i.id}>{i.name}</option>
                ))}
              </select>
            </FormField>
          </div>

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

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
        </div>

        {/* ── Columna derecha: campos custom del catálogo ───────────────────── */}
        {hasCustomFields && (
          <div className="rounded-lg border border-border bg-muted/20 p-5 flex flex-col gap-4 lg:sticky lg:top-4">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Información adicional
              </p>
              {selectedItem && (
                <span className="text-xs text-muted-foreground truncate">
                  {selectedItem.name}
                </span>
              )}
            </div>
            {fields.map((f: ServiceCatalogField) => (
              <div key={f.id} className="flex flex-col gap-1">
                <FieldPreview
                  field={f}
                  value={customValues[f.id] ?? ""}
                  onChange={(v) => setCustomValue(f.id, v)}
                />
                {errors[`cv_${f.id}`] && (
                  <p className="text-xs text-destructive">{errors[`cv_${f.id}`]}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Error global */}
      {errors.submit && (
        <p className="text-sm text-destructive">{errors.submit}</p>
      )}

      {/* Botones — siempre abajo, ocupando ancho completo del form */}
      <div className="flex gap-3 pt-1">
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
