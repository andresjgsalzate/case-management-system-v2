"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Star } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { Badge } from "@/components/atoms/Badge";
import type { ApiResponse } from "@/lib/types";

interface Priority {
  id: string;
  name: string;
  level: number;
  color: string;
  is_default: boolean;
  is_active: boolean;
}

const LEVEL_LABELS: Record<number, string> = { 1: "Baja", 2: "Media", 3: "Alta", 4: "Crítica" };

function usePriorities() {
  return useQuery({
    queryKey: ["case-priorities"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Priority[]>>("/case-priorities");
      return data.data ?? [];
    },
  });
}

function ColorDot({ color }: { color: string }) {
  return <span className="inline-block h-3 w-3 rounded-full border border-border" style={{ backgroundColor: color }} />;
}

export default function PrioritiesSettingsPage() {
  const qc = useQueryClient();
  const { data: priorities = [], isLoading } = usePriorities();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", level: 2, color: "#3B82F6", is_default: false });
  const [error, setError] = useState("");

  const createMutation = useMutation({
    mutationFn: (body: typeof form) => apiClient.post("/case-priorities", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case-priorities"] });
      setShowForm(false);
      setForm({ name: "", level: 2, color: "#3B82F6", is_default: false });
      setError("");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Error al crear prioridad");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/case-priorities/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case-priorities"] }),
  });

  const sorted = [...priorities].sort((a, b) => a.level - b.level);

  return (
    <div className="flex flex-col gap-5 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Prioridades</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Niveles de urgencia para los casos</p>
        </div>
        <button
          type="button"
          onClick={() => { setShowForm((v) => !v); setError(""); }}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Nueva prioridad
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-lg border border-primary/30 bg-card p-4 flex flex-col gap-3">
          <p className="text-sm font-medium text-foreground">Nueva prioridad</p>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Nombre</label>
              <input
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Ej: Urgente"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Nivel (1 = más bajo)</label>
              <input
                type="number"
                min={1} max={10}
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.level}
                onChange={(e) => setForm((f) => ({ ...f, level: Number(e.target.value) }))}
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
            <div className="flex items-center gap-2 pt-4">
              <input
                type="checkbox"
                id="is_default"
                checked={form.is_default}
                onChange={(e) => setForm((f) => ({ ...f, is_default: e.target.checked }))}
                className="h-4 w-4 rounded border-border"
              />
              <label htmlFor="is_default" className="text-sm text-foreground">Prioridad por defecto</label>
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

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Prioridad</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Nivel</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Estado</th>
              <th className="px-4 py-3 w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sorted.length === 0 && !isLoading && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-muted-foreground">Sin prioridades</td></tr>
            )}
            {sorted.map((p) => (
              <tr key={p.id} className="hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <ColorDot color={p.color} />
                    <span className="font-medium text-foreground">{p.name}</span>
                    {p.is_default && <Star className="h-3.5 w-3.5 text-yellow-500 fill-yellow-500" />}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <Badge variant="outline" className="text-xs">{LEVEL_LABELS[p.level] ?? `Nivel ${p.level}`}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={p.is_active ? "success" : "outline"} className="text-xs">
                    {p.is_active ? "Activa" : "Inactiva"}
                  </Badge>
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => { if (confirm(`¿Desactivar prioridad "${p.name}"?`)) deleteMutation.mutate(p.id); }}
                    className="text-muted-foreground hover:text-destructive transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
