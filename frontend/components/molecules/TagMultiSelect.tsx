"use client";

import { useMemo, useState } from "react";
import { X, Plus } from "lucide-react";
import { useKBTags, useCreateKBTag } from "@/hooks/useKB";

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
  const createTag = useCreateKBTag();
  const [search, setSearch] = useState("");

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
          placeholder="Buscar o agregar tag…"
          className="flex w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        {(search.trim() || filtered.length > 0) && (
          <div className="absolute z-10 mt-1 max-h-48 w-full overflow-y-auto rounded-md border border-border bg-popover shadow-md">
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
            {allowCreate && search.trim() && !exactMatch && (
              <button
                type="button"
                onClick={handleCreate}
                disabled={createTag.isPending}
                className="flex w-full items-center gap-1.5 border-t border-border px-3 py-1.5 text-left text-sm text-primary hover:bg-muted"
              >
                <Plus className="h-3 w-3" />
                Crear tag &ldquo;{search.trim()}&rdquo;
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
