"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useForensicArtifacts } from "@/hooks/useForensicArtifacts";
import { apiClient } from "@/lib/apiClient";
import type { ApiResponse, ForensicArtifact } from "@/lib/types";

export default function ForensicArtifactsAdminPage() {
  const [search, setSearch] = useState("");
  const queryClient = useQueryClient();

  const artifactsQuery = useForensicArtifacts({
    search: search || undefined,
    include_destructive: true,
  });
  const artifacts = artifactsQuery.data ?? [];

  const syncMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/forensic/artifacts/sync");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["forensic-artifacts"] });
    },
  });

  const toggleFeaturedMutation = useMutation({
    mutationFn: async (artifact: ForensicArtifact) => {
      const { data } = await apiClient.patch<ApiResponse<ForensicArtifact>>(
        `/forensic/artifacts/${artifact.id}`,
        { is_featured: !artifact.is_featured },
      );
      return data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["forensic-artifacts"] });
    },
  });

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">Catálogo de artifacts</h1>
        <button
          type="button"
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="px-3 py-2 bg-blue-600 text-white rounded text-sm disabled:opacity-50"
        >
          {syncMutation.isPending
            ? "Sincronizando..."
            : "Sincronizar ahora"}
        </button>
      </div>

      {syncMutation.error && (
        <div role="alert" className="text-sm text-red-600">
          Error al sincronizar: {syncMutation.error.message}
        </div>
      )}

      <input
        type="text"
        placeholder="Buscar artifact por nombre o descripción..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-md border rounded px-3 py-2"
      />

      {artifactsQuery.isLoading && (
        <div className="text-sm text-gray-500">Cargando catálogo...</div>
      )}

      {!artifactsQuery.isLoading && artifacts.length === 0 && (
        <div className="text-sm text-gray-500">
          Catálogo vacío. Ejecuta &quot;Sincronizar ahora&quot; para poblar
          desde Velociraptor.
        </div>
      )}

      {artifacts.length > 0 && (
        <table className="w-full text-sm">
          <thead className="bg-gray-100">
            <tr>
              <th className="text-left p-2">⭐</th>
              <th className="text-left p-2">Nombre</th>
              <th className="text-left p-2">Tipo</th>
              <th className="text-left p-2">Categoría</th>
              <th className="text-left p-2">☠ Destructivo</th>
              <th className="text-left p-2">🔍 Evidencia</th>
              <th className="text-left p-2">Sistemas</th>
            </tr>
          </thead>
          <tbody>
            {artifacts.map((a) => (
              <tr key={a.id} className="border-b hover:bg-gray-50">
                <td className="p-2">
                  <input
                    type="checkbox"
                    aria-label={`Featured: ${a.name}`}
                    checked={a.is_featured}
                    disabled={toggleFeaturedMutation.isPending}
                    onChange={() => toggleFeaturedMutation.mutate(a)}
                  />
                </td>
                <td className="p-2">
                  <div className="font-mono text-xs">{a.name}</div>
                  {a.description && (
                    <div className="text-xs text-gray-500 mt-0.5">
                      {a.description}
                    </div>
                  )}
                </td>
                <td className="p-2">{a.artifact_type}</td>
                <td className="p-2">{a.category ?? "—"}</td>
                <td className="p-2">
                  {a.is_destructive ? (
                    <span title="Destructivo">☑</span>
                  ) : (
                    "☐"
                  )}
                </td>
                <td className="p-2">
                  {a.requires_evidence_handling ? "☑" : "☐"}
                </td>
                <td className="p-2 text-xs text-gray-600">
                  {a.supported_os.join(", ") || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
