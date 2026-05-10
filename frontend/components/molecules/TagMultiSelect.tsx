"use client";

import { useMemo, useState } from "react";
import { X, Plus, TrendingUp } from "lucide-react";
import { useKBTags, useCreateKBTag, usePopularKBTags } from "@/hooks/useKB";

interface TagMultiSelectProps {
  value: string[];
  onChange: (ids: string[]) => void;
  allowCreate?: boolean;
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

export function TagMultiSelect({ value, onChange, allowCreate = true }: TagMultiSelectProps) {
  const { data: tags = [] } = useKBTags();
  const { data: popularTags = [] } = usePopularKBTags(10);
  const createTag = useCreateKBTag();
  const [search, setSearch] = useState("");

  // Filtra los populares que NO están ya seleccionados — evita ruido visual
  const popularAvailable = useMemo(
    () => popularTags.filter((t) => !value.includes(t.id)),
    [popularTags, value]
  );

  const selected = useMemo(
    () => tags.filter((t) => value.includes(t.id)),
    [tags, value]
  );
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return tags.filter((t) => !value.includes(t.id));
    return tags.filter(
      (t) => !value.includes(t.id) && t.name.toLowerCase().includes(q)
    );
  }, [tags, value, search]);

  const exactMatch = tags.some(
    (t) => t.name.toLowerCase() === search.trim().toLowerCase()
  );

  async function handleCreate() {
    const name = search.trim();
    if (!name) return;
    const tag = await createTag.mutateAsync({ name, slug: slugify(name) });
    if (tag) {
      onChange([...value, tag.id]);
      setSearch("");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map((t) => (
            <span
              key={t.id}
              className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-0.5 text-xs text-primary"
            >
              {t.name}
              <button
                type="button"
                onClick={() => onChange(value.filter((id) => id !== t.id))}
                className="hover:text-primary/80"
                aria-label={`Quitar ${t.name}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="relative">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            // Enter: si hay un match exacto o un match parcial, lo agrega; si
            // no hay matches y allowCreate está activo, crea el tag.
            // SIEMPRE preventDefault para que no submita el form contenedor.
            if (e.key !== "Enter") return;
            if (!search.trim()) return;
            e.preventDefault();
            // Match exacto case-insensitive: agrégalo directamente.
            const exact = tags.find(
              (t) =>
                t.name.toLowerCase() === search.trim().toLowerCase() &&
                !value.includes(t.id)
            );
            if (exact) {
              onChange([...value, exact.id]);
              setSearch("");
              return;
            }
            // Si hay matches parciales, toma el primero.
            if (filtered.length > 0) {
              onChange([...value, filtered[0].id]);
              setSearch("");
              return;
            }
            // No hay matches → crear si está permitido.
            if (allowCreate && !createTag.isPending) {
              handleCreate();
            }
          }}
          placeholder="Buscar o agregar tag…"
          className="flex w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        {/* Dropdown solo aparece cuando el usuario escribe Y hay matches o opción de crear.
            "Crear tag X" solo se ofrece si NO hay matches parciales (evita ofrecer crear
            mientras ya existe un tag que coincide). */}
        {search.trim() && (filtered.length > 0 || (allowCreate && !exactMatch && filtered.length === 0)) && (
          <div className="absolute z-50 mt-1 max-h-48 w-full overflow-y-auto rounded-md border border-border bg-card shadow-lg">
            {filtered.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  onChange([...value, t.id]);
                  setSearch("");
                }}
                className="block w-full px-3 py-1.5 text-left text-sm hover:bg-muted"
              >
                {t.name}
              </button>
            ))}
            {allowCreate && search.trim() && !exactMatch && filtered.length === 0 && (
              <button
                type="button"
                onClick={handleCreate}
                disabled={createTag.isPending}
                className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-sm text-primary hover:bg-muted"
              >
                <Plus className="h-3 w-3" />
                Crear tag &ldquo;{search.trim()}&rdquo;
              </button>
            )}
          </div>
        )}
      </div>

      {/* Tags populares — sugerencias de uno-clic. Solo si hay disponibles que
          no estén ya seleccionados. Encerrado en un panel para diferenciarlo
          claramente del resto del formulario. */}
      {popularAvailable.length > 0 && (
        <div className="rounded-md border border-dashed border-border bg-muted/30 p-3 flex flex-col gap-2">
          <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            <TrendingUp className="h-3 w-3" />
            Tags populares
          </p>
          <div className="flex flex-wrap gap-1.5">
            {popularAvailable.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => onChange([...value, t.id])}
                className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-0.5 text-xs text-foreground hover:bg-primary/10 hover:border-primary/40 hover:text-primary transition-colors"
                title={`Agregar tag "${t.name}"`}
              >
                <Plus className="h-3 w-3" />
                {t.name}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
