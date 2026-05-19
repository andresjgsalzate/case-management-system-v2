"use client";

import { Pencil, Power, Trash2, Workflow as WorkflowIcon } from "lucide-react";
import { useState } from "react";

import {
  useDeleteN8nWorkflow,
  useN8nWorkflows,
  useUpdateN8nWorkflow,
} from "@/hooks/useN8nWorkflows";
import type { N8nWorkflow } from "@/lib/types";

interface Props {
  onEdit: (wf: N8nWorkflow) => void;
}

export function N8nWorkflowsTable({ onEdit }: Props) {
  const { data, isLoading, error } = useN8nWorkflows();
  const update = useUpdateN8nWorkflow();
  const del = useDeleteN8nWorkflow();
  const [busyId, setBusyId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <p className="p-4 text-sm text-muted-foreground">Cargando workflows…</p>
    );
  }
  if (error) {
    return (
      <p className="p-4 text-sm text-red-600">Error al cargar workflows.</p>
    );
  }
  if (!data || data.length === 0) {
    return (
      <p className="p-4 text-sm text-muted-foreground">
        Sin workflows registrados. Crea el primero con &quot;+ Nuevo workflow&quot;.
      </p>
    );
  }

  async function handleToggleActive(wf: N8nWorkflow) {
    setBusyId(wf.id);
    try {
      await update.mutateAsync({
        id: wf.id,
        body: { is_active: !wf.is_active },
      });
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(wf: N8nWorkflow) {
    if (!confirm(`¿Eliminar el workflow "${wf.name}"? Esta acción no se puede deshacer.`)) {
      return;
    }
    setBusyId(wf.id);
    try {
      await del.mutateAsync(wf.id);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="overflow-auto">
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/40 text-left">
          <tr>
            <th className="px-3 py-2 font-medium">Nombre</th>
            <th className="px-3 py-2 font-medium">Scope</th>
            <th className="px-3 py-2 font-medium">URL</th>
            <th className="px-3 py-2 font-medium">Aprobación</th>
            <th className="px-3 py-2 font-medium">Estado</th>
            <th className="px-3 py-2 font-medium text-right">Acciones</th>
          </tr>
        </thead>
        <tbody>
          {data.map((wf) => (
            <tr key={wf.id} className="border-b last:border-0 hover:bg-muted/30">
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <WorkflowIcon className="h-4 w-4 text-muted-foreground shrink-0" />
                  <div>
                    <p className="font-medium">{wf.name}</p>
                    {wf.description && (
                      <p className="text-xs text-muted-foreground">{wf.description}</p>
                    )}
                  </div>
                </div>
              </td>
              <td className="px-3 py-2">
                {wf.tenant_id === null ? (
                  <span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">
                    global
                  </span>
                ) : (
                  <span className="text-xs text-muted-foreground">tenant</span>
                )}
              </td>
              <td className="px-3 py-2 max-w-[280px]">
                <code className="text-xs text-muted-foreground truncate block" title={wf.workflow_url}>
                  {wf.workflow_url}
                </code>
              </td>
              <td className="px-3 py-2 text-xs">
                {wf.requires_approval ? (
                  <span className="text-amber-600">requiere</span>
                ) : (
                  <span className="text-muted-foreground">no</span>
                )}
              </td>
              <td className="px-3 py-2">
                <span
                  className={`text-xs ${
                    wf.is_active ? "text-emerald-600" : "text-muted-foreground"
                  }`}
                >
                  {wf.is_active ? "activo" : "inactivo"}
                </span>
              </td>
              <td className="px-3 py-2">
                <div className="flex items-center justify-end gap-1">
                  <button
                    type="button"
                    onClick={() => handleToggleActive(wf)}
                    disabled={busyId === wf.id}
                    title={wf.is_active ? "Desactivar" : "Activar"}
                    className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
                  >
                    <Power className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onEdit(wf)}
                    title="Editar"
                    className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(wf)}
                    disabled={busyId === wf.id}
                    title="Eliminar"
                    className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive disabled:opacity-40"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
