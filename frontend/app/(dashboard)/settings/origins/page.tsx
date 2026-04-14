"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Globe, Pencil, Check, X } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import { Badge } from "@/components/atoms/Badge";
import type { ApiResponse } from "@/lib/types";

interface Origin {
  id: string;
  name: string;
  code: string;
  is_active: boolean;
}

function useOrigins() {
  return useQuery({
    queryKey: ["origins"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Origin[]>>("/origins");
      return data.data ?? [];
    },
  });
}

export default function OriginsSettingsPage() {
  const confirm = useConfirm();
  const qc = useQueryClient();
  const { data: origins = [], isLoading } = useOrigins();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", code: "" });
  const [error, setError] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", code: "" });

  const createMutation = useMutation({
    mutationFn: (body: { name: string; code: string }) => apiClient.post("/origins", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["origins"] });
      setShowForm(false);
      setForm({ name: "", code: "" });
      setError("");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Error al crear origen");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { name: string; code: string } }) =>
      apiClient.patch(`/origins/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["origins"] });
      setEditId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/origins/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["origins"] }),
  });

  async function handleDelete(id: string, name: string) {
    const ok = await confirm({ description: `¿Desactivar el origen "${name}"?` });
    if (ok) deleteMutation.mutate(id);
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Orígenes</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Canales por los que llegan los casos (email, chat, teléfono…)</p>
        </div>
        <button
          type="button"
          onClick={() => { setShowForm((v) => !v); setError(""); }}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Nuevo origen
        </button>
      </div>

      {showForm && (
        <div className="rounded-lg border border-primary/30 bg-card p-4 flex flex-col gap-3">
          <p className="text-sm font-medium">Nuevo origen</p>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Nombre</label>
              <input
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Ej: WhatsApp"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Código</label>
              <input
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary uppercase"
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                placeholder="Ej: WHATSAPP"
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground">Cancelar</button>
            <button
              type="button"
              disabled={!form.name.trim() || !form.code.trim() || createMutation.isPending}
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
              {["Canal", "Código", "Estado", ""].map((col) => (
                <th key={col} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {origins.length === 0 && !isLoading && (
              <tr><td colSpan={4} className="px-4 py-10 text-center text-sm text-muted-foreground">Sin orígenes configurados</td></tr>
            )}
            {origins.map((o) =>
              editId === o.id ? (
                <tr key={o.id} className="bg-muted/20">
                  <td className="px-4 py-2">
                    <input
                      className="px-2 py-1.5 text-sm rounded border border-primary bg-background focus:outline-none w-full"
                      value={editForm.name}
                      onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                      placeholder="Nombre"
                      autoFocus
                    />
                  </td>
                  <td className="px-4 py-2">
                    <input
                      className="px-2 py-1.5 text-sm rounded border border-border bg-background focus:outline-none w-full font-mono uppercase"
                      value={editForm.code}
                      onChange={(e) => setEditForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                      placeholder="CÓDIGO"
                    />
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={o.is_active ? "success" : "outline"} className="text-xs">
                      {o.is_active ? "Activo" : "Inactivo"}
                    </Badge>
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        disabled={!editForm.name.trim() || !editForm.code.trim() || updateMutation.isPending}
                        onClick={() => updateMutation.mutate({ id: o.id, body: editForm })}
                        className="text-green-600 hover:text-green-700 disabled:opacity-40"
                      >
                        <Check className="h-4 w-4" />
                      </button>
                      <button type="button" onClick={() => setEditId(null)} className="text-muted-foreground hover:text-foreground">
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr key={o.id} className="hover:bg-muted/30 transition-colors group">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Globe className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium text-foreground">{o.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs bg-muted px-2 py-0.5 rounded">{o.code}</span>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={o.is_active ? "success" : "outline"} className="text-xs">
                      {o.is_active ? "Activo" : "Inactivo"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => { setEditId(o.id); setEditForm({ name: o.name, code: o.code }); }}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(o.id, o.name)}
                        className="text-muted-foreground hover:text-destructive transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
