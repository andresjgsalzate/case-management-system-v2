"use client";

import { useEffect, useState } from "react";
import { Archive, Search } from "lucide-react";
import { useCaseSearch } from "@/hooks/useCases";

interface CasePickerProps {
  excludeIds?: string[];
  onSelect: (caseId: string, caseNumber: string) => void;
  onCancel: () => void;
}

export function CasePicker({ excludeIds = [], onSelect, onCancel }: CasePickerProps) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");

  // Debounce 250ms — evita llamar al backend en cada tecla
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 250);
    return () => clearTimeout(t);
  }, [query]);

  // Endpoint global: busca activos + archivados respetando RBAC
  const { data: cases = [], isFetching } = useCaseSearch(debounced, 25);

  const filtered = cases.filter((c) => !excludeIds.includes(c.id)).slice(0, 15);

  return (
    <div className="rounded-md border border-border bg-background p-3 flex flex-col gap-2">
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar por número o título…"
          className="w-full rounded-md border border-border bg-background pl-8 pr-3 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>
      <div className="max-h-56 overflow-y-auto flex flex-col gap-1">
        {!debounced.trim() && (
          <p className="text-xs text-muted-foreground px-2">
            Escribe el número o parte del título para buscar.
          </p>
        )}
        {debounced.trim() && isFetching && (
          <p className="text-xs text-muted-foreground px-2">Buscando…</p>
        )}
        {debounced.trim() && !isFetching && filtered.length === 0 && (
          <p className="text-xs text-muted-foreground px-2">Sin resultados.</p>
        )}
        {filtered.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => onSelect(c.id, c.case_number)}
            className="flex items-center gap-2 text-left rounded-md px-2 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            <span className="font-mono text-[11px] text-muted-foreground shrink-0">
              {c.case_number}
            </span>
            <span className="flex-1 text-foreground truncate">{c.title}</span>
            {c.is_archived && (
              <span className="flex items-center gap-1 text-[10px] text-muted-foreground shrink-0">
                <Archive className="h-3 w-3" />
                Archivado
              </span>
            )}
          </button>
        ))}
      </div>
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onCancel}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}
