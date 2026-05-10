"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, X, Archive } from "lucide-react";
import { useCaseSearch } from "@/hooks/useCases";
import { Spinner } from "@/components/atoms/Spinner";
import { StatusBadge } from "@/components/molecules/StatusBadge";
import { cn } from "@/lib/utils";

export function GlobalCaseSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [highlight, setHighlight] = useState(0);

  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: results = [], isFetching } = useCaseSearch(debounced);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => { setHighlight(0); }, [debounced]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 10);
  }, [open]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  function go(caseId: string) {
    router.push(`/cases/${caseId}`);
    setOpen(false);
    setQ("");
    setDebounced("");
  }

  function onInputKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!results.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => (h + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => (h - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const pick = results[highlight];
      if (pick) go(pick.id);
    }
  }

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="Buscar caso (Ctrl+K)"
        className={cn(
          "flex items-center justify-center h-8 w-8 rounded-md",
          "text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        )}
      >
        <Search className="h-4 w-4" />
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-50 w-96 rounded-lg border border-border bg-card shadow-lg overflow-hidden">
          <div className="relative flex items-center border-b border-border">
            <Search className="absolute left-3 h-4 w-4 text-muted-foreground pointer-events-none" />
            <input
              ref={inputRef}
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={onInputKey}
              placeholder="Buscar por número o título…"
              className="h-10 w-full bg-transparent pl-9 pr-9 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
            />
            {q && (
              <button
                type="button"
                onClick={() => { setQ(""); setDebounced(""); inputRef.current?.focus(); }}
                className="absolute right-2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {!debounced.trim() && (
              <p className="px-3 py-4 text-xs text-muted-foreground text-center">
                Escribe al menos 1 carácter para buscar. Busca en casos activos y archivados.
              </p>
            )}
            {debounced.trim() && isFetching && (
              <div className="flex items-center justify-center py-6">
                <Spinner className="h-4 w-4" />
              </div>
            )}
            {debounced.trim() && !isFetching && results.length === 0 && (
              <p className="px-3 py-4 text-xs text-muted-foreground text-center">
                Sin resultados para &ldquo;{debounced}&rdquo;.
              </p>
            )}
            {results.map((c, i) => (
              <button
                key={c.id}
                type="button"
                onClick={() => go(c.id)}
                onMouseEnter={() => setHighlight(i)}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-2 text-left border-b border-border/50 last:border-b-0 transition-colors",
                  i === highlight ? "bg-muted" : "hover:bg-muted/60"
                )}
              >
                <span className="font-mono text-[11px] text-muted-foreground shrink-0">
                  {c.case_number}
                </span>
                <span className="flex-1 text-sm text-foreground truncate">{c.title}</span>
                {c.is_archived ? (
                  <span className="flex items-center gap-1 text-[10px] text-muted-foreground shrink-0">
                    <Archive className="h-3 w-3" />
                    Archivado
                  </span>
                ) : (
                  <StatusBadge status={c.status_name} />
                )}
              </button>
            ))}
          </div>

          <div className="px-3 py-1.5 border-t border-border bg-muted/30 text-[10px] text-muted-foreground flex items-center justify-between">
            <span>↑↓ navegar · Enter abrir · Esc cerrar</span>
            <span>Ctrl+K</span>
          </div>
        </div>
      )}
    </div>
  );
}
