"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import {
  useCreateServiceCategory,
  useUpdateServiceCategory,
} from "@/hooks/useServiceCatalog";
import type { ServiceCatalogCategory } from "@/lib/types";
import { slugify, extractApiError } from "@/lib/utils";

interface Props {
  mode: "create" | "edit";
  category?: ServiceCatalogCategory;
  onClose: () => void;
  /** Llamado solo en creación exitosa, con la categoría creada. */
  onCreated?: (created: ServiceCatalogCategory) => void;
}

const COLORS = [
  "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
  "#EC4899", "#06B6D4", "#6366F1", "#84CC16", "#F97316",
];

export function CategoryModal({ mode, category, onClose, onCreated }: Props) {
  const isEdit = mode === "edit";
  const [name, setName] = useState(category?.name ?? "");
  const [slug, setSlug] = useState(category?.slug ?? "");
  const [description, setDescription] = useState(category?.description ?? "");
  const [color, setColor] = useState(category?.color ?? COLORS[0]);
  const [isActive, setIsActive] = useState(category?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);

  const create = useCreateServiceCategory();
  const update = useUpdateServiceCategory();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (isEdit && category) {
        await update.mutateAsync({
          id: category.id,
          dto: { name, description, color, is_active: isActive },
        });
      } else {
        const created = await create.mutateAsync({
          name,
          slug: slug || slugify(name),
          description: description || undefined,
          color,
        });
        onCreated?.(created);
      }
      onClose();
    } catch (err: unknown) {
      setError(extractApiError(err, "Error al guardar la categoría"));
    }
  }

  const busy = create.isPending || update.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-md flex flex-col">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">
            {isEdit ? "Editar categoría" : "Nueva categoría"}
          </h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-5 py-4 flex flex-col gap-4">
          <Field label="Nombre" required>
            <input
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (!isEdit && !slug) setSlug(slugify(e.target.value));
              }}
              required
              minLength={2}
              maxLength={200}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </Field>

          {!isEdit && (
            <Field label="Slug (URL)" required>
              <input
                type="text"
                value={slug}
                onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                required
                minLength={2}
                maxLength={100}
                pattern="^[a-z0-9][a-z0-9\-]*$"
                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="ej: correo-electronico"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Mínimo 2 caracteres. Solo minúsculas, números y guiones. Debe empezar con letra o número.
                No se puede cambiar después.
              </p>
            </Field>
          )}

          <Field label="Descripción">
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={1000}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </Field>

          <Field label="Color">
            <div className="flex gap-2 flex-wrap">
              {COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  className={`h-7 w-7 rounded-md border-2 transition-transform ${
                    color === c ? "border-foreground scale-110" : "border-transparent"
                  }`}
                  style={{ backgroundColor: c }}
                  aria-label={c}
                />
              ))}
            </div>
          </Field>

          {isEdit && (
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-foreground">Categoría activa</span>
            </label>
          )}

          {error && (
            <p className="text-sm text-destructive bg-destructive/10 rounded-md px-3 py-2">{error}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={onClose} disabled={busy}>
              Cancelar
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Guardando…" : "Guardar"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-foreground">
        {label} {required && <span className="text-destructive">*</span>}
      </label>
      {children}
    </div>
  );
}
