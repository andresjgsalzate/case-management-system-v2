"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Check, X, Building2, Circle } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import { Badge } from "@/components/atoms/Badge";
import type { ApiResponse } from "@/lib/types";

interface Tenant {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

function useTenants() {
  return useQuery({
    queryKey: ["tenants"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Tenant[]>>("/tenants");
      return data.data ?? [];
    },
  });
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");
}

const inputCls =
  "px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary w-full";

export default function TenantsSettingsPage() {
  const confirm = useConfirm();
  const qc = useQueryClient();
  const { data: tenants = [], isLoading } = useTenants();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", description: "" });
  const [error, setError] = useState("");

  const [editId, setEditId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", description: "" });

  const createMutation = useMutation({
    mutationFn: (body: { name: string; slug: string; description?: string }) =>
      apiClient.post("/tenants", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenants"] });
      setShowForm(false);
      setForm({ name: "", slug: "", description: "" });
      setError("");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Error al crear el tenant");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { name?: string; description?: string } }) =>
      apiClient.patch(`/tenants/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenants"] });
      setEditId(null);
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Error al actualizar");
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiClient.patch(`/tenants/${id}`, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenants"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/tenants/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenants"] }),
  });

  async function handleDelete(id: string, name: string) {
    const ok = await confirm({
      description: `¿Eliminar el tenant "${name}"? Esta acción no se puede deshacer.`,
    });
    if (ok) deleteMutation.mutate(id);
  }

  function handleNameChange(name: string) {
    setForm((f) => ({ ...f, name, slug: slugify(name) }));
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Tenants</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Organizaciones o clientes con datos aislados dentro del sistema
          </p>
        </div>
        <button
          type="button"
          onClick={() => { setShowForm((v) => !v); setError(""); }}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Nuevo tenant
        </button>
      </div>

      {/* Formulario de creación */}
      {showForm && (
        <div className="rounded-lg border border-primary/30 bg-card p-4 flex flex-col gap-3">
          <p className="text-sm font-medium">Nuevo tenant</p>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Nombre</label>
              <input
                className={inputCls}
                value={form.name}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="Ej: Acme Corp"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Slug</label>
              <input
                className={`${inputCls} font-mono`}
                value={form.slug}
                onChange={(e) => setForm((f) => ({ ...f, slug: slugify(e.target.value) }))}
                placeholder="acme-corp"
              />
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Descripción (opcional)</label>
            <input
              className={inputCls}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Breve descripción del tenant"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={() => { setShowForm(false); setError(""); }}
              className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              Cancelar
            </button>
            <button
              type="button"
              disabled={!form.name.trim() || !form.slug.trim() || createMutation.isPending}
              onClick={() =>
                createMutation.mutate({
                  name: form.name.trim(),
                  slug: form.slug.trim(),
                  description: form.description.trim() || undefined,
                })
              }
              className="px-3 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {createMutation.isPending ? "Guardando…" : "Crear"}
            </button>
          </div>
        </div>
      )}

      {isLoading && <div className="flex justify-center py-16"><Spinner size="lg" /></div>}

      {/* Tabla */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              {["Tenant", "Slug", "Estado", "Creado", ""].map((col) => (
                <th
                  key={col}
                  className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {tenants.length === 0 && !isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-sm text-muted-foreground">
                  Sin tenants configurados
                </td>
              </tr>
            )}
            {tenants.map((t) =>
              editId === t.id ? (
                <tr key={t.id} className="bg-muted/20">
                  <td className="px-4 py-2" colSpan={2}>
                    <div className="flex flex-col gap-1.5">
                      <input
                        className={inputCls}
                        value={editForm.name}
                        onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                        placeholder="Nombre"
                        autoFocus
                      />
                      <input
                        className={inputCls}
                        value={editForm.description}
                        onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                        placeholder="Descripción"
                      />
                    </div>
                  </td>
                  <td className="px-4 py-2" />
                  <td className="px-4 py-2" />
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        disabled={!editForm.name.trim() || updateMutation.isPending}
                        onClick={() =>
                          updateMutation.mutate({
                            id: t.id,
                            body: {
                              name: editForm.name.trim(),
                              description: editForm.description.trim() || undefined,
                            },
                          })
                        }
                        className="text-green-600 hover:text-green-700 disabled:opacity-40"
                      >
                        <Check className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditId(null)}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr key={t.id} className="hover:bg-muted/30 transition-colors group">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
                      <div>
                        <p className="font-medium text-foreground">{t.name}</p>
                        {t.description && (
                          <p className="text-xs text-muted-foreground">{t.description}</p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs bg-muted px-2 py-0.5 rounded">{t.slug}</span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => toggleMutation.mutate({ id: t.id, is_active: !t.is_active })}
                      className="flex items-center gap-1.5 hover:opacity-70 transition-opacity"
                      title={t.is_active ? "Click para desactivar" : "Click para activar"}
                    >
                      <Circle
                        className={`h-2 w-2 fill-current ${t.is_active ? "text-green-500" : "text-muted-foreground"}`}
                      />
                      <Badge variant={t.is_active ? "success" : "outline"} className="text-xs">
                        {t.is_active ? "Activo" : "Inactivo"}
                      </Badge>
                    </button>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(t.created_at).toLocaleDateString("es-MX")}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={() => {
                          setEditId(t.id);
                          setEditForm({ name: t.name, description: t.description ?? "" });
                        }}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(t.id, t.name)}
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

      {/* Info sobre asociación de usuarios */}
      <div className="rounded-lg border border-border bg-muted/20 p-4 text-sm text-muted-foreground">
        <p className="font-medium text-foreground mb-1">¿Cómo asignar usuarios a un tenant?</p>
        <p>
          Ve a <span className="font-medium text-foreground">Configuración → Usuarios</span>, edita
          un usuario y selecciona el tenant correspondiente. El usuario heredará ese tenant en todos
          sus casos, equipos y datos del sistema.
        </p>
      </div>
    </div>
  );
}
