"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import type { ApiResponse } from "@/lib/types";

interface CaseSearchResult {
  id: string;
  case_number: string;
  title: string;
}

interface CasePickerProps {
  excludeIds?: string[];
  onSelect: (caseId: string, caseNumber: string) => void;
  onCancel: () => void;
}

export function CasePicker({ excludeIds = [], onSelect, onCancel }: CasePickerProps) {
  const [query, setQuery] = useState("");

  const { data: cases = [], isLoading } = useQuery({
    queryKey: ["cases-search", query],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<{ data: CaseSearchResult[] }>>(
        "/cases",
        { params: { search: query || undefined, page: 1, page_size: 20 } }
      );
      const items = (data.data as unknown as CaseSearchResult[]) ?? [];
      return items;
    },
    staleTime: 30_000,
  });

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return cases
      .filter((c) => !excludeIds.includes(c.id))
      .filter((c) =>
        !q ||
        c.case_number.toLowerCase().includes(q) ||
        c.title.toLowerCase().includes(q)
      )
      .slice(0, 10);
  }, [cases, query, excludeIds]);

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
        {isLoading && <p className="text-xs text-muted-foreground px-2">Buscando…</p>}
        {!isLoading && filtered.length === 0 && (
          <p className="text-xs text-muted-foreground px-2">Sin resultados</p>
        )}
        {filtered.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => onSelect(c.id, c.case_number)}
            className="text-left rounded-md px-2 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            <span className="font-medium">{c.case_number}</span>
            <span className="text-muted-foreground ml-2 truncate">{c.title}</span>
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
