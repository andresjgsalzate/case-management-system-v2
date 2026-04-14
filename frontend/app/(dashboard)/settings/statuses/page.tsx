"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ArrowRight, Flag, Pencil, Check, X } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { useConfirm } from "@/components/providers/ConfirmProvider";
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
  pauses_sla: boolean;
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

const BLANK_FORM = { name: "", color: "#6B7280", order: 0, is_initial: false, is_final: false, pauses_sla: false };

export default function StatusesSettingsPage() {
  const confirm = useConfirm();
  const qc = useQueryClient();
  const { data: statuses = [], isLoading } = useStatuses();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(BLANK_FORM);
  const [error, setError] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", color: "#6B7280", order: 0, is_initial: false, is_final: false, pauses_sla: false });

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

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: typeof editForm }) =>
      apiClient.patch(`/case-statuses/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case-statuses"] });
      setEditId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/case-statuses/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case-statuses"] }),
  });

  async function handleDelete(id: string, name: string) {
    const ok = await confirm({ description: `¿Eliminar el estado "${name}"?` });
    if (ok) deleteMutation.mutate(id);
  }

  return (
    <div className="flex flex-col gap-5">
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
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.pauses_sla} onChange={(e) => setForm((f) => ({ ...f, pauses_sla: e.target.checked }))} className="h-4 w-4 rounded" />
                <span className="text-sm text-amber-700">Pausa SLA</span>
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
        {statuses.map((s) =>
          editId === s.id ? (
            <div key={s.id} className="rounded-lg border border-primary/50 bg-card p-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={editForm.color}
                    onChange={(e) => setEditForm((f) => ({ ...f, color: e.target.value }))}
                    className="h-9 w-12 cursor-pointer rounded border border-border p-0.5"
                  />
                  <input
                    className="px-2 py-1.5 text-sm rounded border border-primary bg-background focus:outline-none flex-1"
                    value={editForm.name}
                    onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Nombre"
                    autoFocus
                  />
                </div>
                <div className="flex items-center gap-2">
                  <label className="text-xs text-muted-foreground shrink-0">Orden</label>
                  <input
                    type="number"
                    className="px-2 py-1.5 text-sm rounded border border-border bg-background focus:outline-none w-20"
                    value={editForm.order}
                    onChange={(e) => setEditForm((f) => ({ ...f, order: Number(e.target.value) }))}
                  />
                </div>
                <div className="flex items-center gap-4 flex-wrap">
                  <label className="flex items-center gap-1.5 cursor-pointer text-sm">
                    <input type="checkbox" checked={editForm.is_initial} onChange={(e) => setEditForm((f) => ({ ...f, is_initial: e.target.checked }))} className="h-4 w-4 rounded" />
                    Inicial
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer text-sm">
                    <input type="checkbox" checked={editForm.is_final} onChange={(e) => setEditForm((f) => ({ ...f, is_final: e.target.checked }))} className="h-4 w-4 rounded" />
                    Final
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer text-sm text-amber-700">
                    <input type="checkbox" checked={editForm.pauses_sla} onChange={(e) => setEditForm((f) => ({ ...f, pauses_sla: e.target.checked }))} className="h-4 w-4 rounded" />
                    Pausa SLA
                  </label>
                </div>
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    disabled={!editForm.name.trim() || updateMutation.isPending}
                    onClick={() => updateMutation.mutate({ id: s.id, body: editForm })}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                  >
                    <Check className="h-3.5 w-3.5" />
                    Guardar
                  </button>
                  <button type="button" onClick={() => setEditId(null)} className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div key={s.id} className="rounded-lg border border-border bg-card p-4 group">
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
                      {s.pauses_sla && <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">Pausa SLA</Badge>}
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
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => { setEditId(s.id); setEditForm({ name: s.name, color: s.color, order: s.order, is_initial: s.is_initial, is_final: s.is_final, pauses_sla: s.pauses_sla }); }}
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(s.id, s.name)}
                    className="text-muted-foreground hover:text-destructive transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          )
        )}
        {statuses.length === 0 && !isLoading && (
          <div className="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">Sin estados configurados</div>
        )}
      </div>
    </div>
  );
}
