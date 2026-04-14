"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Layers, Pencil, Check, X } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import { Badge } from "@/components/atoms/Badge";
import type { ApiResponse } from "@/lib/types";

interface Application {
  id: string;
  name: string;
  code: string;
  description?: string;
  is_active: boolean;
}

function useApplications() {
  return useQuery({
    queryKey: ["applications"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Application[]>>("/applications");
      return data.data ?? [];
    },
  });
}

const BLANK = { name: "", code: "", description: "" };

export default function ApplicationsSettingsPage() {
  const confirm = useConfirm();
  const qc = useQueryClient();
  const { data: apps = [], isLoading } = useApplications();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(BLANK);
  const [error, setError] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", description: "" });

  const createMutation = useMutation({
    mutationFn: (body: typeof form) => apiClient.post("/applications", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      setShowForm(false);
      setForm(BLANK);
      setError("");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Error al crear aplicación");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { name: string; description: string } }) =>
      apiClient.patch(`/applications/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      setEditId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/applications/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  async function handleDelete(id: string, name: string) {
    const ok = await confirm({ description: `¿Desactivar la aplicación "${name}"?` });
    if (ok) deleteMutation.mutate(id);
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Aplicaciones</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Sistemas o productos a los que pertenecen los casos</p>
        </div>
        <button
          type="button"
          onClick={() => { setShowForm((v) => !v); setError(""); }}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Nueva aplicación
        </button>
      </div>

      {showForm && (
        <div className="rounded-lg border border-primary/30 bg-card p-4 flex flex-col gap-3">
          <p className="text-sm font-medium">Nueva aplicación</p>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Nombre</label>
              <input
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Ej: Portal de Clientes"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Código (único)</label>
              <input
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary uppercase"
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                placeholder="Ej: PORTAL"
              />
            </div>
            <div className="col-span-2 flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Descripción (opcional)</label>
              <input
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Breve descripción del sistema"
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
              {["Aplicación", "Código", "Estado", ""].map((col) => (
                <th key={col} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {apps.length === 0 && !isLoading && (
              <tr><td colSpan={4} className="px-4 py-10 text-center text-sm text-muted-foreground">Sin aplicaciones. Crea la primera.</td></tr>
            )}
            {apps.map((app) =>
              editId === app.id ? (
                <tr key={app.id} className="bg-muted/20">
                  <td className="px-4 py-2" colSpan={2}>
                    <div className="flex flex-col gap-1.5">
                      <input
                        className="px-2 py-1.5 text-sm rounded border border-primary bg-background focus:outline-none w-full"
                        value={editForm.name}
                        onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                        placeholder="Nombre"
                        autoFocus
                      />
                      <input
                        className="px-2 py-1.5 text-sm rounded border border-border bg-background focus:outline-none w-full"
                        value={editForm.description}
                        onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                        placeholder="Descripción (opcional)"
                      />
                    </div>
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={app.is_active ? "success" : "outline"} className="text-xs">
                      {app.is_active ? "Activa" : "Inactiva"}
                    </Badge>
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        disabled={!editForm.name.trim() || updateMutation.isPending}
                        onClick={() => updateMutation.mutate({ id: app.id, body: editForm })}
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
                <tr key={app.id} className="hover:bg-muted/30 transition-colors group">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-7 w-7 rounded bg-primary/10 flex items-center justify-center shrink-0">
                        <Layers className="h-3.5 w-3.5 text-primary" />
                      </div>
                      <div>
                        <p className="font-medium text-foreground">{app.name}</p>
                        {app.description && <p className="text-xs text-muted-foreground">{app.description}</p>}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs bg-muted px-2 py-0.5 rounded">{app.code}</span>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={app.is_active ? "success" : "outline"} className="text-xs">
                      {app.is_active ? "Activa" : "Inactiva"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => { setEditId(app.id); setEditForm({ name: app.name, description: app.description ?? "" }); }}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(app.id, app.name)}
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
