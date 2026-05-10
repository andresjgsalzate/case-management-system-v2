"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import {
  useCreateServiceItem,
  useServiceCategories,
} from "@/hooks/useServiceCatalog";
import { useCasePriorities, useTeams } from "@/hooks/useCases";
import { slugify, extractApiError } from "@/lib/utils";

interface Props {
  mode: "create";
  defaultCategoryId?: string;
  onClose: () => void;
}

export function ItemModal({ defaultCategoryId, onClose }: Props) {
  const [categoryId, setCategoryId] = useState(defaultCategoryId ?? "");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [priorityId, setPriorityId] = useState<string>("");
  const [teamId, setTeamId] = useState<string>("");
  const [defaultLevel, setDefaultLevel] = useState<number>(1);
  const [error, setError] = useState<string | null>(null);

  const { data: categories = [] } = useServiceCategories();
  const { data: priorities = [] } = useCasePriorities();
  const { data: teams = [] } = useTeams();

  const create = useCreateServiceItem();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await create.mutateAsync({
        category_id: categoryId,
        name,
        slug: slug || slugify(name),
        description: description || undefined,
        default_priority_id: priorityId || null,
        default_team_id: teamId || null,
        default_level: defaultLevel,
      });
      onClose();
    } catch (err: unknown) {
      setError(extractApiError(err, "Error al guardar el ítem"));
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-lg flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
          <h2 className="text-sm font-semibold text-foreground">Nuevo ítem del catálogo</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-5 py-4 flex flex-col gap-4 overflow-y-auto">
          <Field label="Categoría" required>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              required
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">Selecciona una categoría…</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </Field>

          <Field label="Nombre del ítem" required>
            <input
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (!slug) setSlug(slugify(e.target.value));
              }}
              required
              minLength={2}
              maxLength={200}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="ej: Restablecer contraseña"
            />
          </Field>

          <Field label="Slug (URL)" required>
            <input
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
              required
              pattern="^[a-z0-9][a-z0-9\-]*$"
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </Field>

          <Field label="Descripción">
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Prioridad por defecto">
              <select
                value={priorityId}
                onChange={(e) => setPriorityId(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="">Sin default</option>
                {priorities.map((p: { id: string; name: string }) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </Field>

            <Field label="Equipo por defecto">
              <select
                value={teamId}
                onChange={(e) => setTeamId(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="">Sin default</option>
                {teams.map((t: { id: string; name: string }) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Nivel inicial">
            <input
              type="number"
              min={0}
              max={5}
              value={defaultLevel}
              onChange={(e) => setDefaultLevel(parseInt(e.target.value || "0", 10))}
              className="w-24 h-9 rounded-md border border-input bg-background px-3 text-sm"
            />
            <p className="text-xs text-muted-foreground mt-1">
              N0 reporter · N1 primer nivel · N2 segundo nivel · …
            </p>
          </Field>

          {error && (
            <p className="text-sm text-destructive bg-destructive/10 rounded-md px-3 py-2">{error}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={onClose} disabled={create.isPending}>
              Cancelar
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Guardando…" : "Crear ítem"}
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
