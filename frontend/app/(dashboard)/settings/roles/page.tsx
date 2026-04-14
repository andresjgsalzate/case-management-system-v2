"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Shield, Plus, Trash2, Pencil, Check, X, ChevronDown, ChevronUp, Save } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { Badge } from "@/components/atoms/Badge";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import { formatDate } from "@/lib/utils";
import type { ApiResponse } from "@/lib/types";

interface Permission {
  module: string;
  action: string;
  scope: string;
}

interface Role {
  id: string;
  name: string;
  description?: string;
  permissions?: Permission[];
  created_at: string;
}

// ─── Catálogo de permisos del sistema ────────────────────────────────────────

// Agrupación visual de módulos por categoría
const MODULE_GROUPS = [
  {
    label: "Gestión de casos",
    modules: ["cases", "notes", "attachments", "todos", "time_entries"],
  },
  {
    label: "Configuración de casos",
    modules: ["classification", "dispositions", "sla"],
  },
  {
    label: "Usuarios y acceso",
    modules: ["users", "teams", "roles"],
  },
  {
    label: "Herramientas",
    modules: ["knowledge_base", "automation", "notifications", "search"],
  },
  {
    label: "Reportes y auditoría",
    modules: ["metrics", "audit"],
  },
];

const MODULE_LABELS: Record<string, string> = {
  cases:          "Casos",
  notes:          "Notas internas",
  attachments:    "Adjuntos",
  todos:          "Tareas del caso",
  time_entries:   "Registro de tiempo",
  classification: "Clasificación",
  dispositions:   "Disposiciones",
  sla:            "SLA",
  users:          "Usuarios",
  teams:          "Equipos",
  roles:          "Roles y permisos",
  knowledge_base: "Base de conocimiento",
  automation:     "Automatización",
  notifications:  "Notificaciones",
  search:         "Búsqueda",
  metrics:        "Métricas / Reportes",
  audit:          "Auditoría",
};

const ACTION_LABELS: Record<string, string> = {
  read:       "Ver",
  create:     "Crear",
  update:     "Editar",
  delete:     "Eliminar",
  manage:     "Administrar",
  assign:     "Asignar",
  transition: "Cambiar estado",
  archive:    "Archivar",
  export:     "Exportar",
};

// Catálogo exacto de permisos disponibles por módulo
// (coincide con los PermissionChecker del backend)
const PERMISSION_CATALOG: Record<string, string[]> = {
  // Gestión de casos
  cases:          ["read", "create", "update", "manage", "assign", "transition", "archive", "export"],
  notes:          ["read", "create", "delete"],
  attachments:    ["read", "create", "delete"],
  todos:          ["read", "create"],
  time_entries:   ["read", "create"],
  // Configuración de casos
  classification: ["read", "create", "manage"],
  dispositions:   ["read", "create", "manage"],
  sla:            ["read", "manage"],
  // Usuarios y acceso
  users:          ["read", "create", "update", "delete"],
  teams:          ["read", "manage"],
  roles:          ["read", "manage"],
  // Herramientas
  knowledge_base: ["read", "create", "manage"],
  automation:     ["read", "create", "manage"],
  notifications:  ["read", "create"],
  search:         ["read"],
  // Reportes y auditoría
  metrics:        ["read"],
  audit:          ["read"],
};

// Todas las acciones posibles (para encabezados de columna)
const ALL_ACTIONS = ["read", "create", "update", "delete", "manage", "assign", "transition", "archive", "export"];

// ─── Hooks ───────────────────────────────────────────────────────────────────

function useRoles() {
  return useQuery({
    queryKey: ["roles"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Role[]>>("/roles");
      return data.data ?? [];
    },
  });
}

// ─── Componente de matriz de permisos ────────────────────────────────────────

function PermissionsMatrix({
  roleId,
  current,
  onClose,
}: {
  roleId: string;
  current: Permission[];
  onClose: () => void;
}) {
  const qc = useQueryClient();

  // Estado local: set de "module:action" que están activos
  const [checked, setChecked] = useState<Set<string>>(() => {
    const s = new Set<string>();
    current.forEach((p) => s.add(`${p.module}:${p.action}`));
    return s;
  });

  const saveMutation = useMutation({
    mutationFn: (perms: Permission[]) =>
      apiClient.put(`/roles/${roleId}/permissions`, perms),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["roles"] });
      onClose();
    },
  });

  function toggle(module: string, action: string) {
    const key = `${module}:${action}`;
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function handleSave() {
    const perms: Permission[] = [];
    checked.forEach((key) => {
      const [module, action] = key.split(":");
      perms.push({ module, action, scope: "all" });
    });
    saveMutation.mutate(perms);
  }

  return (
    <div className="mt-3 pt-3 border-t border-border">
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-muted/50 border-b border-border">
              <th className="px-3 py-2 text-left font-medium text-muted-foreground w-44">Módulo</th>
              {ALL_ACTIONS.map((action) => (
                <th key={action} className="px-2 py-2 text-center font-medium text-muted-foreground whitespace-nowrap">
                  {ACTION_LABELS[action]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {MODULE_GROUPS.map((group) => (
              <React.Fragment key={group.label}>
                {/* Separador de grupo */}
                <tr className="bg-muted/30">
                  <td colSpan={ALL_ACTIONS.length + 1} className="px-3 py-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                    {group.label}
                  </td>
                </tr>
                {group.modules.map((module) => {
                  const actions = PERMISSION_CATALOG[module] ?? [];
                  return (
                    <tr key={module} className="hover:bg-muted/20">
                      <td className="px-3 py-2 font-medium text-foreground pl-5">
                        {MODULE_LABELS[module] ?? module}
                      </td>
                      {ALL_ACTIONS.map((action) => {
                        const available = actions.includes(action);
                        const key = `${module}:${action}`;
                        const isChecked = checked.has(key);
                        return (
                          <td key={action} className="px-2 py-2 text-center">
                            {available ? (
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => toggle(module, action)}
                                className="h-4 w-4 rounded border-border accent-primary cursor-pointer"
                              />
                            ) : (
                              <span className="text-muted-foreground/20">·</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-3 mt-3">
        <button
          type="button"
          disabled={saveMutation.isPending}
          onClick={handleSave}
          className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Save className="h-3.5 w-3.5" />
          {saveMutation.isPending ? "Guardando…" : "Guardar permisos"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          Cancelar
        </button>
        <span className="text-xs text-muted-foreground ml-auto">
          {checked.size} permiso{checked.size !== 1 ? "s" : ""} seleccionado{checked.size !== 1 ? "s" : ""}
        </span>
      </div>
    </div>
  );
}

// ─── Página principal ─────────────────────────────────────────────────────────

const ROLE_COLORS: Record<string, "default" | "warning" | "success" | "destructive" | "secondary" | "outline"> = {
  "Super Admin": "destructive",
  "Admin":       "warning",
  "Manager":     "default",
  "Agent":       "secondary",
};

const BLANK_FORM = { name: "", description: "" };

export default function RolesSettingsPage() {
  const confirm = useConfirm();
  const qc = useQueryClient();
  const { data: roles = [], isLoading } = useRoles();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(BLANK_FORM);
  const [formError, setFormError] = useState("");

  // Inline edit de nombre/descripción
  const [editId, setEditId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", description: "" });

  // Panel de permisos expandido por rol
  const [expandedPerms, setExpandedPerms] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (body: typeof form) => apiClient.post("/roles", { ...body, permissions: [] }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["roles"] });
      setShowForm(false);
      setForm(BLANK_FORM);
      setFormError("");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setFormError(msg ?? "Error al crear rol");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { name: string; description: string } }) =>
      apiClient.patch(`/roles/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["roles"] });
      setEditId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/roles/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["roles"] }),
  });

  async function handleDelete(id: string, name: string) {
    const ok = await confirm({ description: `¿Eliminar el rol "${name}"? Esta acción no se puede deshacer.` });
    if (ok) deleteMutation.mutate(id);
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Roles y Permisos</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isLoading ? "Cargando…" : `${roles.length} rol${roles.length !== 1 ? "es" : ""} configurados`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => { setShowForm((v) => !v); setFormError(""); }}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Nuevo rol
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-lg border border-primary/30 bg-card p-4 flex flex-col gap-3">
          <p className="text-sm font-medium">Nuevo rol</p>
          {formError && <p className="text-xs text-destructive">{formError}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Nombre</label>
              <input
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Ej: Supervisor"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">Descripción (opcional)</label>
              <input
                className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Breve descripción del rol"
              />
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
              {createMutation.isPending ? "Creando…" : "Crear rol"}
            </button>
          </div>
        </div>
      )}

      {isLoading && <div className="flex justify-center py-16"><Spinner size="lg" /></div>}

      {/* Role cards */}
      <div className="flex flex-col gap-3">
        {roles.map((role) => {
          const permCount = role.permissions?.length ?? 0;
          const modules = [...new Set(role.permissions?.map((p) => p.module) ?? [])];
          const isEditingName = editId === role.id;
          const isExpandedPerms = expandedPerms === role.id;

          return (
            <div
              key={role.id}
              className="rounded-lg border border-border bg-card p-4 hover:border-primary/20 transition-colors"
            >
              {/* Header row */}
              {isEditingName ? (
                <div className="flex flex-col gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1">
                      <label className="text-xs text-muted-foreground">Nombre</label>
                      <input
                        className="px-2 py-1.5 text-sm rounded border border-primary bg-background focus:outline-none w-full"
                        value={editForm.name}
                        onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                        autoFocus
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-xs text-muted-foreground">Descripción</label>
                      <input
                        className="px-2 py-1.5 text-sm rounded border border-border bg-background focus:outline-none w-full"
                        value={editForm.description}
                        onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                        placeholder="Descripción del rol"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2 justify-end">
                    <button type="button" onClick={() => setEditId(null)} className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground">
                      <X className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      disabled={!editForm.name.trim() || updateMutation.isPending}
                      onClick={() => updateMutation.mutate({ id: role.id, body: editForm })}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    >
                      <Check className="h-3.5 w-3.5" />
                      Guardar
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-md bg-muted flex items-center justify-center shrink-0">
                      <Shield className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground">{role.name}</span>
                        <Badge variant={ROLE_COLORS[role.name] ?? "outline"} className="text-xs">
                          {role.name}
                        </Badge>
                      </div>
                      {role.description && (
                        <p className="text-xs text-muted-foreground mt-0.5">{role.description}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => { setEditId(role.id); setEditForm({ name: role.name, description: role.description ?? "" }); }}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                      title="Editar nombre"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(role.id, role.name)}
                      className="text-muted-foreground hover:text-destructive transition-colors"
                      title="Eliminar rol"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )}

              {/* Stats + permissions toggle */}
              {!isEditingName && (
                <>
                  <div className="mt-3 pt-3 border-t border-border flex items-center gap-4 text-xs text-muted-foreground">
                    <span>{permCount} permiso{permCount !== 1 ? "s" : ""}</span>
                    <span>{modules.length} módulo{modules.length !== 1 ? "s" : ""}</span>
                    <span>Creado {formatDate(role.created_at)}</span>
                    <button
                      type="button"
                      onClick={() => setExpandedPerms(isExpandedPerms ? null : role.id)}
                      className="ml-auto flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors"
                    >
                      {isExpandedPerms ? (
                        <><ChevronUp className="h-3.5 w-3.5" /> Ocultar permisos</>
                      ) : (
                        <><ChevronDown className="h-3.5 w-3.5" /> Editar permisos</>
                      )}
                    </button>
                  </div>

                  {/* Module badges summary (when collapsed) */}
                  {!isExpandedPerms && modules.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {modules.slice(0, 10).map((mod) => (
                        <span key={mod} className="px-1.5 py-0.5 rounded text-xs bg-muted text-muted-foreground capitalize">
                          {MODULE_LABELS[mod] ?? mod}
                        </span>
                      ))}
                      {modules.length > 10 && (
                        <span className="px-1.5 py-0.5 rounded text-xs bg-muted text-muted-foreground">
                          +{modules.length - 10} más
                        </span>
                      )}
                    </div>
                  )}

                  {/* Expanded permissions matrix */}
                  {isExpandedPerms && (
                    <PermissionsMatrix
                      roleId={role.id}
                      current={role.permissions ?? []}
                      onClose={() => setExpandedPerms(null)}
                    />
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
