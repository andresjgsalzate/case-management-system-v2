"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Search, X } from "lucide-react";

import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import {
  useMitreTechniqueSearch,
  type MitreTechnique,
} from "@/hooks/useMitreTechniques";

interface Props {
  open: boolean;
  initialSelected: string[];
  onClose: () => void;
  onSave: (ids: string[]) => void;
}

const TACTIC_COLORS: Record<string, string> = {
  reconnaissance: "bg-slate-100 text-slate-700",
  "resource-development": "bg-slate-100 text-slate-700",
  "initial-access": "bg-blue-100 text-blue-800",
  execution: "bg-indigo-100 text-indigo-800",
  persistence: "bg-purple-100 text-purple-800",
  "privilege-escalation": "bg-fuchsia-100 text-fuchsia-800",
  "defense-evasion": "bg-amber-100 text-amber-800",
  "credential-access": "bg-orange-100 text-orange-800",
  discovery: "bg-emerald-100 text-emerald-800",
  "lateral-movement": "bg-teal-100 text-teal-800",
  collection: "bg-cyan-100 text-cyan-800",
  "command-and-control": "bg-sky-100 text-sky-800",
  exfiltration: "bg-pink-100 text-pink-800",
  impact: "bg-rose-100 text-rose-800",
};

export function MitreTechniquePickerModal({
  open,
  initialSelected,
  onClose,
  onSave,
}: Props) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  // Debounce the query so each keystroke doesn't fire a request.
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 200);
    return () => clearTimeout(t);
  }, [query]);

  // Reset local state every time the modal re-opens.
  useEffect(() => {
    if (open) {
      setQuery("");
      setDebouncedQuery("");
      setSelected(initialSelected);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const { data: results = [], isFetching } = useMitreTechniqueSearch(
    debouncedQuery,
    open,
  );

  const selectedSet = useMemo(() => new Set(selected), [selected]);

  function toggle(id: string) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4">
      <div className="flex h-[80vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg bg-card shadow-xl">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-base font-semibold">
            Buscar técnicas MITRE ATT&amp;CK
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="border-b p-3">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="ID o nombre (ej: T1078, Phishing, Credential Dumping)"
              className="pl-7"
            />
          </div>
          {selected.length > 0 && (
            <p className="mt-2 text-xs text-muted-foreground">
              {selected.length} técnica{selected.length === 1 ? "" : "s"} seleccionada
              {selected.length === 1 ? "" : "s"}
            </p>
          )}
        </div>

        <div className="flex-1 overflow-y-auto">
          {isFetching && results.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">Buscando…</p>
          ) : results.length === 0 ? (
            <p className="p-8 text-sm text-muted-foreground text-center">
              {debouncedQuery
                ? "Sin resultados para esa búsqueda."
                : "Escribe ID o nombre para buscar."}
            </p>
          ) : (
            <ul className="divide-y">
              {results.map((t) => {
                const isSelected = selectedSet.has(t.id);
                return (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => toggle(t.id)}
                      className={`flex w-full items-start gap-3 px-3 py-2 text-left hover:bg-muted/40 ${
                        isSelected ? "bg-primary/5" : ""
                      }`}
                    >
                      <div
                        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                          isSelected
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border bg-background"
                        }`}
                      >
                        {isSelected && <Check className="h-3 w-3" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <code className="font-mono text-xs text-muted-foreground">
                            {t.id}
                          </code>
                          <span className="font-medium">{t.name}</span>
                          {t.is_subtechnique && (
                            <span className="rounded bg-slate-100 px-1 text-[10px] text-slate-600 dark:bg-slate-700/40">
                              sub
                            </span>
                          )}
                        </div>
                        {t.tactics.length > 0 && (
                          <div className="mt-0.5 flex flex-wrap gap-1">
                            {t.tactics.map((tac) => (
                              <span
                                key={tac}
                                className={`rounded px-1.5 py-0.5 text-[10px] ${
                                  TACTIC_COLORS[tac] ??
                                  "bg-slate-100 text-slate-700"
                                }`}
                              >
                                {tac}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={() => onSave(selected)}>
            Guardar ({selected.length})
          </Button>
        </footer>
      </div>
    </div>
  );
}
