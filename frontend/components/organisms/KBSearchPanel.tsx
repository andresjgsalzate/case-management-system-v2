"use client";

import { useState, useCallback, useRef, type KeyboardEvent } from "react";
import { Search, X, Undo2 } from "lucide-react";
import type { Filter } from "@/lib/kb-search";
import { cn } from "@/lib/utils";

interface Props {
  filters: Filter[];
  onFiltersChange: (next: Filter[]) => void;
  placeholder?: string;
  className?: string;
}

export function KBSearchPanel({
  filters,
  onFiltersChange,
  placeholder,
  className,
}: Props) {
  const [current, setCurrent] = useState("");
  const [exactToggle, setExactToggle] = useState(false);
  const [history, setHistory] = useState<Filter[][]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const commit = useCallback(
    (next: Filter[]) => {
      setHistory((h) => [...h, filters]);
      onFiltersChange(next);
    },
    [filters, onFiltersChange],
  );

  const addFilter = useCallback(() => {
    const term = current.trim();
    if (!term) return;
    if (filters.some((f) => f.term === term && f.exact === exactToggle)) {
      setCurrent("");
      return;
    }
    commit([...filters, { term, exact: exactToggle }]);
    setCurrent("");
    setExactToggle(false);
  }, [current, filters, exactToggle, commit]);

  const removeFilter = useCallback(
    (idx: number) => {
      commit(filters.filter((_, i) => i !== idx));
    },
    [filters, commit],
  );

  const undo = useCallback(() => {
    if (history.length === 0) return;
    const prev = history[history.length - 1];
    setHistory((h) => h.slice(0, -1));
    onFiltersChange(prev);
  }, [history, onFiltersChange]);

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addFilter();
    } else if (e.key === "Backspace" && current === "" && filters.length > 0) {
      e.preventDefault();
      removeFilter(filters.length - 1);
    }
  };

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <input
            ref={inputRef}
            type="text"
            value={current}
            placeholder={placeholder ?? "Buscar artículos…"}
            onChange={(e) => setCurrent(e.target.value)}
            onKeyDown={onKeyDown}
            className="w-full h-9 pl-8 pr-3 rounded-md border border-border bg-background text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
          <input
            type="checkbox"
            checked={exactToggle}
            onChange={(e) => setExactToggle(e.target.checked)}
            className="h-3.5 w-3.5 rounded accent-primary"
            aria-label="Exacta"
          />
          Exacta
        </label>
      </div>

      {filters.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs text-muted-foreground">Filtros:</span>
          {filters.map((f, i) => (
            <span
              key={`${f.term}|${f.exact}|${i}`}
              className={cn(
                "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs",
                f.exact
                  ? "bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30"
                  : "bg-primary/10 text-primary",
              )}
            >
              {f.exact && <span className="font-semibold">✓</span>}
              {f.exact && f.term.includes(" ") ? `"${f.term}"` : f.term}
              <button
                type="button"
                onClick={() => removeFilter(i)}
                className="ml-0.5 hover:opacity-70"
                aria-label={`Quitar filtro ${f.term}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          {history.length > 0 && (
            <button
              type="button"
              onClick={undo}
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground ml-1"
            >
              <Undo2 className="h-3 w-3" />
              Deshacer
            </button>
          )}
        </div>
      )}
    </div>
  );
}
