"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ArrowRight, Flag } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { Badge } from "@/components/atoms/Badge";
import type { ApiResponse } from "@/lib/types";

interface CaseStatus {
  id: string;
  name: string;
  slug: string;
  color: string;
  order: number;
  is_initial: boolean;
  is_final: boolean;
  allowed_transitions: string[];
  created_at: string;
}

function useStatuses() {
  return useQuery({
    queryKey: ["case-statuses"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<CaseStatus[]>>("/case-statuses");
      return (data.data ?? []).sort((a, b) => a.order - b.order);
    },
  });
}

function ColorDot({ color }: { color: string }) {
  return <span className="inline-block h-3 w-3 rounded-full border border-border" style={{ backgroundColor: color }} />;
}

const BLANK_FORM = { name: "", color: "#6B7280", order: 0, is_initial: false, is_final: false };

export default function StatusesSettingsPage() {
  const qc = useQueryClient();
  const { data: statuses = [], isLoading } = useStatuses();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(BLANK_FORM);
  const [error, setError] = useState("");

  const createMutation = useMutation({
    mutationFn: (body: typeof form) => apiClient.post("/case-statuses", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case-statuses"] });
      setShowForm(false);
      setForm(BLANK_FORM);
      setError("");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Error al crear estado");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/case-statuses/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case-statuses"] }),
  });

  return (
    <div className="flex flex-col gap-5 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Estados de Caso</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Flujo de estados y transiciones permitidas</p>
        </div>
        <button
          type="button"
          onClick={() => { setShowForm((v) => !v); setError(""); }}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Nuevo estado
        </button>
      </div>

      {showForm && (
        <div className="rounded-lg border border-primary/30 bg-card p-4 flex flex-col gap-3">
          <p className="text-sm font-medium">Nuevo estado</p>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Nombre</label>
              <input
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Ej: En espera"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Orden</label>
              <input
                type="number"
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.order}
                onChange={(e) => setForm((f) => ({ ...f, order: Number(e.target.value) }))}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Color</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={form.color}
                  onChange={(e) => setForm((f) => ({ ...f, color: e.target.value }))}
                  className="h-9 w-12 cursor-pointer rounded border border-border bg-background p-0.5"
                />
                <span className="text-sm text-muted-foreground font-mono">{form.color}</span>
              </div>
            </div>
            <div className="flex flex-col gap-2 pt-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_initial} onChange={(e) => setForm((f) => ({ ...f, is_initial: e.target.checked }))} className="h-4 w-4 rounded" />
                <span className="text-sm">Estado inicial</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_final} onChange={(e) => setForm((f) => ({ ...f, is_final: e.target.checked }))} className="h-4 w-4 rounded" />
                <span className="text-sm">Estado final</span>
              </label>
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground">Cancelar</button>
            <button
              type="button"
              disabled={!form.name.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate(form)}
              className="px-3 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {createMutation.isPending ? "Guardando…" : "Crear"}
            </button>
          </div>
        </div>
      )}

      {isLoading && <div className="flex justify-center py-16"><Spinner size="lg" /></div>}

      <div className="flex flex-col gap-2">
        {statuses.map((s) => (
          <div key={s.id} className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-md flex items-center justify-center shrink-0" style={{ backgroundColor: s.color + "20" }}>
                  <Flag className="h-4 w-4" style={{ color: s.color }} />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <ColorDot color={s.color} />
                    <span className="font-medium text-foreground">{s.name}</span>
                    <span className="text-xs text-muted-foreground font-mono">#{s.order}</span>
                    {s.is_initial && <Badge variant="default" className="text-xs">Inicial</Badge>}
                    {s.is_final && <Badge variant="secondary" className="text-xs">Final</Badge>}
                  </div>
                  {s.allowed_transitions.length > 0 && (
                    <div className="flex items-center gap-1 mt-1 flex-wrap">
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      {s.allowed_transitions.map((t) => (
                        <span key={t} className="text-xs text-muted-foreground px-1.5 py-0.5 rounded bg-muted">{t}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => { if (confirm(`¿Eliminar estado "${s.name}"?`)) deleteMutation.mutate(s.id); }}
                className="text-muted-foreground hover:text-destructive transition-colors shrink-0"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
        {statuses.length === 0 && !isLoading && (
          <div className="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">Sin estados configurados</div>
        )}
      </div>
    </div>
  );
}
