"use client";

import { Search } from "lucide-react";
import { useState } from "react";

import type { AuditExplorerFilters, AuditSource } from "@/lib/types";

const ALL_SOURCES: AuditSource[] = ["activity", "audit", "inbound_event"];

interface Props {
  initial?: AuditExplorerFilters;
  onSearch: (filters: AuditExplorerFilters) => void;
  onExport?: (filters: AuditExplorerFilters) => void;
}

export function AuditExplorerFiltersForm({
  initial, onSearch, onExport,
}: Props) {
  const [caseId, setCaseId] = useState(initial?.case_id ?? "");
  const [search, setSearch] = useState(initial?.search ?? "");
  const [dateFrom, setDateFrom] = useState(initial?.date_from ?? "");
  const [dateTo, setDateTo] = useState(initial?.date_to ?? "");
  const [sources, setSources] = useState<AuditSource[]>(
    initial?.sources ?? [...ALL_SOURCES],
  );

  function toggleSource(s: AuditSource) {
    setSources((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s],
    );
  }

  function buildFilters(): AuditExplorerFilters {
    return {
      case_id: caseId.trim() || null,
      search: search.trim() || null,
      date_from: dateFrom ? new Date(dateFrom).toISOString() : null,
      date_to: dateTo ? new Date(dateTo).toISOString() : null,
      sources: sources.length === ALL_SOURCES.length ? undefined : sources,
      limit: 200,
      offset: 0,
    };
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSearch(buildFilters());
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3 rounded border bg-card p-3 text-xs"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="block">
          <span className="mb-1 block font-medium">Caso (ID)</span>
          <input
            type="text"
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
            placeholder="uuid del caso"
            className="w-full rounded border px-2 py-1 font-mono"
          />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">Búsqueda</span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="texto en summary"
            className="w-full rounded border px-2 py-1"
          />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">Desde</span>
          <input
            type="datetime-local"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="w-full rounded border px-2 py-1"
          />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">Hasta</span>
          <input
            type="datetime-local"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="w-full rounded border px-2 py-1"
          />
        </label>
      </div>

      <fieldset>
        <legend className="mb-1 font-medium">Fuentes</legend>
        <div className="flex flex-wrap gap-3">
          {ALL_SOURCES.map((s) => (
            <label key={s} className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={sources.includes(s)}
                onChange={() => toggleSource(s)}
              />
              <span className="font-mono">{s}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="flex justify-end gap-2 border-t pt-2">
        {onExport ? (
          <button
            type="button"
            onClick={() => onExport(buildFilters())}
            className="rounded border px-3 py-1 hover:bg-muted"
          >
            Exportar CSV
          </button>
        ) : null}
        <button
          type="submit"
          className="inline-flex items-center gap-1 rounded bg-blue-600 px-3 py-1 font-medium text-white hover:bg-blue-700"
        >
          <Search className="h-3 w-3" /> Buscar
        </button>
      </div>
    </form>
  );
}
