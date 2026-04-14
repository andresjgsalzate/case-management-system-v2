"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  UserPlus, CheckCircle, XCircle, Mail, Pencil, Check, X, UserX, UserCheck,
} from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Avatar } from "@/components/atoms/Avatar";
import { Badge } from "@/components/atoms/Badge";
import { Spinner } from "@/components/atoms/Spinner";
import { SearchBar } from "@/components/molecules/SearchBar";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import { formatDate } from "@/lib/utils";
import type { ApiResponse } from "@/lib/types";

interface User {
  id: string;
  email: string;
  full_name: string;
  role_id: string | null;
  team_id: string | null;
  tenant_id: string | null;
  is_active: boolean;
  email_notifications: boolean;
  avatar_url: string | null;
  created_at: string;
}

interface Role  { id: string; name: string }
interface Team  { id: string; name: string }
interface Tenant { id: string; name: string; slug: string }

const inputCls =
  "px-2 py-1.5 text-sm rounded border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary w-full";
const selectCls =
  "px-2 py-1.5 text-sm rounded border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary w-full";

function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: User[]; total: number }>(
        "/users?page=1&page_size=100"
      );
      return data.data ?? [];
    },
  });
}

function useRoles() {
  return useQuery({
    queryKey: ["roles"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Role[]>>("/roles");
      return data.data ?? [];
    },
  });
}

function useTeams() {
  return useQuery({
    queryKey: ["teams"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Team[]>>("/teams");
      return data.data ?? [];
    },
  });
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

const BLANK_FORM = {
  email: "", full_name: "", password: "",
  role_id: "", team_id: "", tenant_id: "",
};

type EditForm = {
  full_name: string;
  role_id: string;
  team_id: string;
  tenant_id: string;
};

export default function UsersSettingsPage() {
  const confirm = useConfirm();
  const qc = useQueryClient();

  const { data: users = [], isLoading } = useUsers();
  const { data: roles = [] } = useRoles();
  const { data: teams = [] } = useTeams();
  const { data: tenants = [] } = useTenants();

  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(BLANK_FORM);
  const [formError, setFormError] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<EditForm>({
    full_name: "", role_id: "", team_id: "", tenant_id: "",
  });

  const createMutation = useMutation({
    mutationFn: (body: typeof form) =>
      apiClient.post("/users", {
        ...body,
        role_id:   body.role_id   || undefined,
        team_id:   body.team_id   || undefined,
        tenant_id: body.tenant_id || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setShowForm(false);
      setForm(BLANK_FORM);
      setFormError("");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setFormError(msg ?? "Error al crear usuario");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<EditForm> }) =>
      apiClient.patch(`/users/${id}`, {
        full_name:  body.full_name  || undefined,
        role_id:    body.role_id    || null,
        team_id:    body.team_id    || null,
        tenant_id:  body.tenant_id  || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setEditId(null);
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setFormError(msg ?? "Error al actualizar usuario");
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => apiClient.post(`/users/${id}/deactivate`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const reactivateMutation = useMutation({
    mutationFn: (id: string) => apiClient.post(`/users/${id}/reactivate`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  async function handleDeactivate(id: string, name: string) {
    const ok = await confirm({
      description: `¿Desactivar al usuario "${name}"? Ya no podrá iniciar sesión.`,
    });
    if (ok) deactivateMutation.mutate(id);
  }

  async function handleReactivate(id: string, name: string) {
    const ok = await confirm({ description: `¿Reactivar al usuario "${name}"?` });
    if (ok) reactivateMutation.mutate(id);
  }

  function startEdit(user: User) {
    setEditId(user.id);
    setEditForm({
      full_name:  user.full_name,
      role_id:    user.role_id   ?? "",
      team_id:    user.team_id   ?? "",
      tenant_id:  user.tenant_id ?? "",
    });
    setFormError("");
  }

  const filtered = users.filter(
    (u) =>
      u.full_name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Usuarios</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isLoading
              ? "Cargando…"
              : `${users.length} usuario${users.length !== 1 ? "s" : ""} en el sistema`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => { setShowForm((v) => !v); setFormError(""); }}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <UserPlus className="h-4 w-4" />
          Nuevo usuario
        </button>
      </div>

      {/* Formulario de creación */}
      {showForm && (
        <div className="rounded-lg border border-primary/30 bg-card p-4 flex flex-col gap-3">
          <p className="text-sm font-medium">Nuevo usuario</p>
          {formError && <p className="text-xs text-destructive">{formError}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Nombre completo</label>
              <input
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.full_name}
                onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                placeholder="Nombre Apellido"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Email</label>
              <input
                type="email"
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="usuario@empresa.com"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Contraseña inicial</label>
              <input
                type="password"
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="Mín. 6 caracteres"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Rol</label>
              <select
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.role_id}
                onChange={(e) => setForm((f) => ({ ...f, role_id: e.target.value }))}
              >
                <option value="">Sin rol</option>
                {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Equipo</label>
              <select
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.team_id}
                onChange={(e) => setForm((f) => ({ ...f, team_id: e.target.value }))}
              >
                <option value="">Sin equipo</option>
                {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Tenant</label>
              <select
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.tenant_id}
                onChange={(e) => setForm((f) => ({ ...f, tenant_id: e.target.value }))}
              >
                <option value="">Sin tenant (global)</option>
                {tenants.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={() => { setShowForm(false); setFormError(""); }}
              className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              Cancelar
            </button>
            <button
              type="button"
              disabled={
                !form.full_name.trim() ||
                !form.email.trim() ||
                form.password.length < 6 ||
                createMutation.isPending
              }
              onClick={() => createMutation.mutate(form)}
              className="px-3 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {createMutation.isPending ? "Creando…" : "Crear usuario"}
            </button>
          </div>
        </div>
      )}

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Buscar por nombre o email…"
        className="max-w-sm"
      />

      {isLoading && <div className="flex justify-center py-16"><Spinner size="lg" /></div>}

      {!isLoading && (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                {["Usuario", "Email", "Rol", "Equipo", "Tenant", "Estado", "Creado", ""].map((col) => (
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
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-sm text-muted-foreground">
                    No hay usuarios que coincidan
                  </td>
                </tr>
              ) : (
                filtered.map((user) =>
                  editId === user.id ? (
                    /* ── Fila edición ── */
                    <tr key={user.id} className="bg-muted/20">
                      <td className="px-3 py-2">
                        <input
                          className={inputCls}
                          value={editForm.full_name}
                          onChange={(e) => setEditForm((f) => ({ ...f, full_name: e.target.value }))}
                          autoFocus
                          placeholder="Nombre completo"
                        />
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">{user.email}</td>
                      <td className="px-3 py-2">
                        <select
                          className={selectCls}
                          value={editForm.role_id}
                          onChange={(e) => setEditForm((f) => ({ ...f, role_id: e.target.value }))}
                        >
                          <option value="">Sin rol</option>
                          {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <select
                          className={selectCls}
                          value={editForm.team_id}
                          onChange={(e) => setEditForm((f) => ({ ...f, team_id: e.target.value }))}
                        >
                          <option value="">Sin equipo</option>
                          {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <select
                          className={selectCls}
                          value={editForm.tenant_id}
                          onChange={(e) => setEditForm((f) => ({ ...f, tenant_id: e.target.value }))}
                        >
                          <option value="">Sin tenant</option>
                          {tenants.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <Badge
                          variant={user.is_active ? "success" : "outline"}
                          className="text-xs w-fit"
                        >
                          {user.is_active ? "Activo" : "Inactivo"}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">
                        {formatDate(user.created_at)}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            disabled={!editForm.full_name.trim() || updateMutation.isPending}
                            onClick={() =>
                              updateMutation.mutate({ id: user.id, body: editForm })
                            }
                            className="text-green-600 hover:text-green-700 disabled:opacity-40"
                            title="Guardar"
                          >
                            <Check className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditId(null)}
                            className="text-muted-foreground hover:text-foreground"
                            title="Cancelar"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    /* ── Fila vista ── */
                    <tr key={user.id} className="hover:bg-muted/30 transition-colors group">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar name={user.full_name} size="sm" />
                          <span className="font-medium text-foreground">{user.full_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5 text-muted-foreground text-xs">
                          <Mail className="h-3.5 w-3.5 shrink-0" />
                          {user.email}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {roles.find((r) => r.id === user.role_id)?.name ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {teams.find((t) => t.id === user.team_id)?.name ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {tenants.find((t) => t.id === user.tenant_id)?.name ?? (
                          <span className="italic">Global</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {user.is_active ? (
                          <Badge variant="success" className="flex items-center gap-1 w-fit text-xs">
                            <CheckCircle className="h-3 w-3" />
                            Activo
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="flex items-center gap-1 w-fit text-xs text-muted-foreground">
                            <XCircle className="h-3 w-3" />
                            Inactivo
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                        {formatDate(user.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => startEdit(user)}
                            className="text-muted-foreground hover:text-foreground transition-colors"
                            title="Editar"
                          >
                            <Pencil className="h-4 w-4" />
                          </button>
                          {user.is_active ? (
                            <button
                              type="button"
                              onClick={() => handleDeactivate(user.id, user.full_name)}
                              className="text-muted-foreground hover:text-destructive transition-colors"
                              title="Desactivar"
                            >
                              <UserX className="h-4 w-4" />
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleReactivate(user.id, user.full_name)}
                              className="text-muted-foreground hover:text-green-600 transition-colors"
                              title="Reactivar"
                            >
                              <UserCheck className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                )
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
