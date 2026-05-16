"use client";

import { Check, ChevronDown, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { useSecurityTaxonomies } from "@/hooks/useSecurityTaxonomies";
import type { SecurityTaxonomy, TaxonomyDefaultCaseType } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TaxonomySelectorProps {
  value: string | null;
  onChange: (taxonomyId: string | null, taxonomy: SecurityTaxonomy | null) => void;
  /**
   * If set, filter the list to taxonomies whose default_case_type matches.
   * 'event' shows event taxonomies; 'incident' shows incident taxonomies.
   * Undefined → show all.
   */
  caseTypeFilter?: TaxonomyDefaultCaseType;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

export function TaxonomySelector({
  value,
  onChange,
  caseTypeFilter,
  disabled = false,
  placeholder = "— Seleccionar taxonomía —",
  className,
}: TaxonomySelectorProps) {
  const { data: taxonomies, isLoading } = useSecurityTaxonomies();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const rootRef = useRef<HTMLDivElement | null>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const selected = useMemo(() => {
    if (!value || !taxonomies) return null;
    return taxonomies.find((t) => t.id === value) ?? null;
  }, [value, taxonomies]);

  const filtered = useMemo(() => {
    if (!taxonomies) return [] as SecurityTaxonomy[];
    const term = search.trim().toLowerCase();
    return taxonomies.filter((t) => {
      if (caseTypeFilter && t.default_case_type !== caseTypeFilter) return false;
      if (!t.is_active) return false;
      if (!term) return true;
      return (
        t.tuic_code.toLowerCase().includes(term) ||
        t.name.toLowerCase().includes(term) ||
        (t.attack_type ?? "").toLowerCase().includes(term)
      );
    });
  }, [taxonomies, search, caseTypeFilter]);

  function selectTaxonomy(t: SecurityTaxonomy) {
    onChange(t.id, t);
    setOpen(false);
    setSearch("");
  }

  function clearSelection(e: React.MouseEvent) {
    e.stopPropagation();
    onChange(null, null);
  }

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(!open)}
        className={cn(
          "flex w-full items-center justify-between gap-2 rounded border bg-background px-3 py-1.5 text-left text-sm",
          "hover:border-blue-400 focus:border-blue-500 focus:outline-none",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {selected ? (
          <span className="flex flex-1 items-baseline gap-2 truncate">
            <span className="font-mono text-xs text-muted-foreground">
              {selected.tuic_code}
            </span>
            <span className="truncate">{selected.name}</span>
          </span>
        ) : (
          <span className="text-muted-foreground">{placeholder}</span>
        )}
        <div className="flex items-center gap-1">
          {selected ? (
            <span
              onClick={clearSelection}
              className="rounded px-1 text-xs text-muted-foreground hover:bg-muted"
              role="button"
              aria-label="Limpiar selección"
            >
              ×
            </span>
          ) : null}
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </div>
      </button>

      {open ? (
        <div className="absolute z-10 mt-1 w-full max-h-72 overflow-hidden rounded border bg-background shadow-lg">
          <div className="relative border-b p-2">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              autoFocus
              placeholder="Buscar por TUIC, nombre, tipo de ataque..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded border bg-background py-1 pl-7 pr-2 text-sm"
            />
          </div>
          <ul role="listbox" className="max-h-56 overflow-y-auto">
            {isLoading ? (
              <li className="p-2 text-xs text-muted-foreground">Cargando...</li>
            ) : filtered.length === 0 ? (
              <li className="p-2 text-xs text-muted-foreground">
                Sin resultados.
              </li>
            ) : (
              filtered.map((t) => (
                <li
                  key={t.id}
                  role="option"
                  aria-selected={t.id === value}
                  onClick={() => selectTaxonomy(t)}
                  className={cn(
                    "flex cursor-pointer items-baseline gap-2 px-3 py-1.5 text-sm hover:bg-muted",
                    t.id === value && "bg-blue-50 dark:bg-blue-950/40",
                  )}
                >
                  {t.id === value ? (
                    <Check className="h-3.5 w-3.5 text-blue-600" />
                  ) : (
                    <span className="inline-block w-3.5" />
                  )}
                  <span className="flex-1 min-w-0">
                    <span className="font-mono text-xs text-muted-foreground">
                      {t.tuic_code}
                    </span>{" "}
                    <span className="truncate">{t.name}</span>
                    {t.attack_type ? (
                      <span className="ml-1 text-[10px] text-muted-foreground">
                        · {t.attack_type}
                      </span>
                    ) : null}
                  </span>
                  {t.tenant_id !== null ? (
                    <span className="text-[10px] text-purple-700 dark:text-purple-400">
                      override
                    </span>
                  ) : null}
                </li>
              ))
            )}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
