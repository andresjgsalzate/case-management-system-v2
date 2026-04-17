"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Archive, RotateCcw, Search } from "lucide-react";
import { useArchivedCases, useRestoreCase } from "@/hooks/useCases";
import { SearchBar } from "@/components/molecules/SearchBar";
import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { Spinner } from "@/components/atoms/Spinner";
import { formatRelative } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { Case } from "@/lib/types";

const PAGE_SIZE = 20;

// ── Restore button ─────────────────────────────────────────────────────────────

function RestoreButton({ caseId, caseNumber }: { caseId: string; caseNumber: string }) {
  const [confirming, setConfirming] = useState(false);
  const restore = useRestoreCase(caseId);

  if (confirming) {
    return (
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-muted-foreground whitespace-nowrap">¿Restaurar {caseNumber}?</span>
        <Button
          size="sm"
          variant="default"
          disabled={restore.isPending}
          onClick={(e) => {
            e.stopPropagation();
            restore.mutate(undefined, { onSuccess: () => setConfirming(false) });
          }}
        >
          {restore.isPending ? <Spinner className="h-3 w-3" /> : "Sí"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={(e) => { e.stopPropagation(); setConfirming(false); }}
        >
          No
        </Button>
      </div>
    );
  }

  return (
    <Button
      size="sm"
      variant="outline"
      onClick={(e) => { e.stopPropagation(); setConfirming(true); }}
      title="Restaurar caso"
    >
      <RotateCcw className="h-3.5 w-3.5 mr-1" />
      Restaurar
    </Button>
  );
}

// ── Complexity badge ───────────────────────────────────────────────────────────

const COMPLEXITY_LABELS: Record<string, string> = {
  simple: "Simple",
  moderate: "Moderado",
  complex: "Complejo",
};

// ── Page ───────────────────────────────────────────────────────────────────────

export default function ArchivePage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);

  // Debounce search so we don't fire on every keystroke
  const handleSearch = (value: string) => {
    setSearch(value);
    setPage(1);
    clearTimeout((handleSearch as any)._timer);
    (handleSearch as any)._timer = setTimeout(() => setDebouncedSearch(value), 350);
  };

  const { data, isLoading, isFetching } = useArchivedCases({
    search: debouncedSearch || undefined,
    page,
    page_size: PAGE_SIZE,
  });

  const cases: Case[] = data?.data ?? [];
  const total: number = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-col gap-5">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
            <Archive className="h-4.5 w-4.5 text-slate-500" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-foreground">Archivo</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {isLoading
                ? "Cargando…"
                : `${total} caso${total !== 1 ? "s" : ""} archivado${total !== 1 ? "s" : ""}`}
            </p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="flex items-center gap-3">
        <SearchBar
          value={search}
          onChange={handleSearch}
          placeholder="Buscar por título o número…"
          className="sm:w-72"
        />
        {isFetching && !isLoading && (
          <Spinner className="h-4 w-4 text-muted-foreground" />
        )}
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Spinner className="h-6 w-6" />
          </div>
        ) : cases.length === 0 ? (
          <EmptyState hasSearch={!!debouncedSearch} />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-28">Número</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Título</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-32 hidden sm:table-cell">Estado</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-28 hidden md:table-cell">Prioridad</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-32 hidden lg:table-cell">Cerrado</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-32 hidden lg:table-cell">Archivado</th>
                <th className="text-right px-4 py-3 w-36" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {cases.map((c) => (
                <CaseRow
                  key={c.id}
                  case={c}
                  onClick={() => router.push(`/archive/${c.id}`)}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <Pagination page={page} totalPages={totalPages} onChange={setPage} />
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function CaseRow({ case: c, onClick }: { case: Case; onClick: () => void }) {
  return (
    <tr
      className="hover:bg-muted/30 cursor-pointer transition-colors"
      onClick={onClick}
    >
      <td className="px-4 py-3">
        <span className="font-mono text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
          {c.case_number}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className="font-medium text-foreground line-clamp-1">{c.title}</span>
        {c.complexity && (
          <span className="text-xs text-muted-foreground ml-1">
            · {COMPLEXITY_LABELS[c.complexity] ?? c.complexity}
          </span>
        )}
      </td>
      <td className="px-4 py-3 hidden sm:table-cell">
        <StatusDot color={c.status_color} label={c.status_name} />
      </td>
      <td className="px-4 py-3 hidden md:table-cell">
        <PriorityDot color={c.priority_color} label={c.priority_name} />
      </td>
      <td className="px-4 py-3 hidden lg:table-cell text-xs text-muted-foreground">
        {c.closed_at ? formatRelative(c.closed_at) : "—"}
      </td>
      <td className="px-4 py-3 hidden lg:table-cell text-xs text-muted-foreground">
        {c.archived_at ? formatRelative(c.archived_at) : "—"}
      </td>
      <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
        <RestoreButton caseId={c.id} caseNumber={c.case_number} />
      </td>
    </tr>
  );
}

function StatusDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="h-2 w-2 rounded-full shrink-0"
        style={{ backgroundColor: color || "#94a3b8" }}
      />
      <span className="text-xs text-foreground">{label}</span>
    </span>
  );
}

function PriorityDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="h-2 w-2 rounded-full shrink-0"
        style={{ backgroundColor: color || "#94a3b8" }}
      />
      <span className="text-xs text-foreground">{label}</span>
    </span>
  );
}

function EmptyState({ hasSearch }: { hasSearch: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
      {hasSearch ? (
        <>
          <Search className="h-10 w-10 text-muted-foreground/30" />
          <p className="text-sm font-medium text-foreground">Sin resultados</p>
          <p className="text-xs text-muted-foreground">
            No se encontraron casos archivados que coincidan con la búsqueda.
          </p>
        </>
      ) : (
        <>
          <Archive className="h-10 w-10 text-muted-foreground/30" />
          <p className="text-sm font-medium text-foreground">Archivo vacío</p>
          <p className="text-xs text-muted-foreground">
            Los casos cerrados que se archiven aparecerán aquí.
          </p>
        </>
      )}
    </div>
  );
}

function Pagination({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (p: number) => void;
}) {
  return (
    <div className="flex items-center justify-center gap-2">
      <Button
        size="sm"
        variant="outline"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        Anterior
      </Button>
      <span className="text-sm text-muted-foreground">
        Página {page} de {totalPages}
      </span>
      <Button
        size="sm"
        variant="outline"
        disabled={page >= totalPages}
        onClick={() => onChange(page + 1)}
      >
        Siguiente
      </Button>
    </div>
  );
}
