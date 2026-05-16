"use client";

import { Power, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  useIntegrationSources,
  useRotateSourceSecret,
  useSoftDeleteIntegrationSource,
  useUpdateIntegrationSource,
} from "@/hooks/useIntegrationSources";
import type { RotateSecretResponse } from "@/lib/types";

interface Props {
  /** Called when a rotate operation reveals a fresh secret. The page shows a modal. */
  onSecretRevealed: (rotated: RotateSecretResponse, sourceName: string) => void;
}

export function IntegrationSourcesTable({ onSecretRevealed }: Props) {
  const { data, isLoading, error } = useIntegrationSources();
  const rotate = useRotateSourceSecret();
  const softDelete = useSoftDeleteIntegrationSource();
  const update = useUpdateIntegrationSource();
  const [busyId, setBusyId] = useState<string | null>(null);

  if (isLoading) {
    return <p className="p-4 text-sm text-muted-foreground">Cargando fuentes…</p>;
  }
  if (error) {
    return <p className="p-4 text-sm text-red-600">Error al cargar fuentes.</p>;
  }
  if (!data || data.length === 0) {
    return (
      <p className="p-4 text-sm text-muted-foreground">
        Sin fuentes configuradas. Crea la primera con &quot;+ Nueva fuente&quot;.
      </p>
    );
  }

  async function handleRotate(id: string, name: string) {
    setBusyId(id);
    try {
      const result = await rotate.mutateAsync(id);
      onSecretRevealed(result, name);
    } finally {
      setBusyId(null);
    }
  }

  async function handleToggleActive(id: string, active: boolean) {
    setBusyId(id);
    try {
      await update.mutateAsync({ id, payload: { is_active: active } });
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Desactivar la fuente "${name}"? Los eventos pendientes seguirán visibles.`)) {
      return;
    }
    setBusyId(id);
    try {
      await softDelete.mutateAsync(id);
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
            <th className="px-3 py-2 font-medium">Tipo</th>
            <th className="px-3 py-2 font-medium">Auth</th>
            <th className="px-3 py-2 font-medium">Estado</th>
            <th className="px-3 py-2 font-medium text-right">Eventos (recibidos / fallidos)</th>
            <th className="px-3 py-2 font-medium">Último evento</th>
            <th className="px-3 py-2 font-medium text-right">Acciones</th>
          </tr>
        </thead>
        <tbody>
          {data.map((s) => {
            const isBusy = busyId === s.id;
            return (
              <tr key={s.id} className="border-b last:border-0 hover:bg-muted/30">
                <td className="px-3 py-2 font-medium">{s.name}</td>
                <td className="px-3 py-2 font-mono text-xs">{s.source_type}</td>
                <td className="px-3 py-2 font-mono text-xs">{s.auth_method}</td>
                <td className="px-3 py-2 text-xs">
                  {s.is_active ? (
                    <span className="rounded bg-green-100 px-1.5 py-0.5 text-green-800">
                      activa
                    </span>
                  ) : (
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-600">
                      inactiva
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-right font-mono">
                  {s.total_events_received.toLocaleString()} /
                  <span className={s.total_events_failed ? "text-red-600" : ""}>
                    {" "}{s.total_events_failed.toLocaleString()}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">
                  {s.last_event_received_at
                    ? new Date(s.last_event_received_at).toLocaleString()
                    : "—"}
                </td>
                <td className="px-3 py-2">
                  <div className="flex justify-end gap-1">
                    <button
                      type="button"
                      onClick={() => handleRotate(s.id, s.name)}
                      disabled={isBusy}
                      title="Rotar el secreto (la nueva clave se mostrará una sola vez)"
                      className="rounded p-1 hover:bg-muted disabled:opacity-50"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleToggleActive(s.id, !s.is_active)}
                      disabled={isBusy}
                      title={s.is_active ? "Desactivar" : "Activar"}
                      className="rounded p-1 hover:bg-muted disabled:opacity-50"
                    >
                      <Power
                        className={`h-3.5 w-3.5 ${s.is_active ? "text-green-700" : "text-gray-400"}`}
                      />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(s.id, s.name)}
                      disabled={isBusy}
                      title="Soft-delete (marca inactiva)"
                      className="rounded p-1 text-red-600 hover:bg-red-50 disabled:opacity-50"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
