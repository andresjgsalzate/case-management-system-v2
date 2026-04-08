"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Hash, Save, Eye } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import type { ApiResponse } from "@/lib/types";

interface NumberSequence {
  prefix: string;
  padding: number;
  last_number: number;
  preview: string;
}

function useSequence() {
  return useQuery({
    queryKey: ["case-number-sequence"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<NumberSequence>>("/cases/settings/number-sequence");
      return data.data!;
    },
  });
}

export default function CaseNumbersSettingsPage() {
  const qc = useQueryClient();
  const { data: seq, isLoading } = useSequence();

  const [prefix, setPrefix] = useState("CASE");
  const [padding, setPadding] = useState(4);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (seq) {
      setPrefix(seq.prefix);
      setPadding(seq.padding);
    }
  }, [seq]);

  const preview = `${prefix.toUpperCase() || "CASE"}-${"1".padStart(padding, "0")}`;

  const mutation = useMutation({
    mutationFn: () => apiClient.patch("/cases/settings/number-sequence", { prefix, padding }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case-number-sequence"] });
      setSaved(true);
      setError("");
      setTimeout(() => setSaved(false), 2500);
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Error al guardar");
    },
  });

  const dirty = seq ? prefix !== seq.prefix || padding !== seq.padding : false;

  return (
    <div className="flex flex-col gap-6 max-w-lg">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Numeración de Casos</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Configura el formato con el que se generan los números de caso
        </p>
      </div>

      {isLoading && <div className="flex justify-center py-16"><Spinner size="lg" /></div>}

      {!isLoading && seq && (
        <>
          {/* Preview card */}
          <div className="rounded-lg border border-border bg-card p-5 flex items-center gap-4">
            <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <Hash className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1">Vista previa del próximo caso</p>
              <p className="text-2xl font-mono font-bold text-foreground tracking-wider">{preview}</p>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground">Último número generado</p>
              <p className="text-xl font-semibold text-foreground mt-1">{seq.last_number.toLocaleString()}</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground">Próximo número</p>
              <p className="text-xl font-semibold text-foreground mt-1">{(seq.last_number + 1).toLocaleString()}</p>
            </div>
          </div>

          {/* Config form */}
          <div className="rounded-lg border border-border bg-card p-5 flex flex-col gap-4">
            <p className="text-sm font-medium text-foreground">Configuración del formato</p>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-muted-foreground">
                Prefijo <span className="text-xs">(máx. 4 caracteres alfanuméricos)</span>
              </label>
              <input
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary uppercase font-mono w-32"
                value={prefix}
                maxLength={4}
                onChange={(e) => setPrefix(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))}
                placeholder="CASE"
              />
              <p className="text-xs text-muted-foreground">Texto que aparece antes del número. Ej: TICKET, INC, REQ</p>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-muted-foreground">
                Dígitos mínimos (padding)
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={1} max={8}
                  value={padding}
                  onChange={(e) => setPadding(Number(e.target.value))}
                  className="w-40 accent-primary"
                />
                <span className="text-sm font-mono w-4 text-foreground">{padding}</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Número mínimo de dígitos. Con padding {padding}: {String(1).padStart(padding, "0")}, {String(42).padStart(padding, "0")}, {String(1000).padStart(padding, "0")}
              </p>
            </div>

            <div className="pt-1 flex items-center gap-3">
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Eye className="h-3.5 w-3.5" /> Resultado: <span className="font-mono font-medium text-foreground">{preview}</span>
              </p>
            </div>

            {error && <p className="text-xs text-destructive">{error}</p>}

            <div className="flex items-center gap-3 pt-1">
              <button
                type="button"
                disabled={!dirty || mutation.isPending}
                onClick={() => mutation.mutate()}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                <Save className="h-4 w-4" />
                {mutation.isPending ? "Guardando…" : "Guardar cambios"}
              </button>
              {saved && (
                <span className="text-sm text-green-600 dark:text-green-400">Guardado correctamente</span>
              )}
              {!dirty && !saved && (
                <span className="text-xs text-muted-foreground">Sin cambios pendientes</span>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-4">
            <p className="text-sm text-amber-800 dark:text-amber-200 font-medium">Nota importante</p>
            <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
              Cambiar el prefijo o padding solo afecta a los casos creados <strong>a partir de ahora</strong>.
              Los casos existentes conservarán su número original.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
