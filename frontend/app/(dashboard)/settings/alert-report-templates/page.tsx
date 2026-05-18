"use client";

import Link from "next/link";
import { useState } from "react";

import {
  useAlertReportTemplates,
  useCreateAlertReportTemplate,
  useDeleteAlertReportTemplate,
  useSetDefaultTemplate,
} from "@/hooks/useAlertReportTemplates";

export default function AlertReportTemplatesListPage() {
  const [includeInactive, setIncludeInactive] = useState(false);
  const query = useAlertReportTemplates({ include_inactive: includeInactive });
  const createMutation = useCreateAlertReportTemplate();
  const deleteMutation = useDeleteAlertReportTemplate();
  const setDefaultMutation = useSetDefaultTemplate();

  const templates = query.data ?? [];

  async function handleCreate() {
    const name = window.prompt("Nombre de la plantilla?");
    if (!name) return;
    const code = window.prompt(
      "Código (slug, p.ej. soc_executive):",
    );
    if (!code) return;
    try {
      await createMutation.mutateAsync({
        name,
        code,
        header_config: {
          show_logo: true,
          show_classification: true,
          show_case_metadata_table: true,
          title_template: "DESCRIPCIÓN GENERAL DE LA GESTIÓN DE LA ALERTA",
        },
        footer_config: {
          show_page_numbers: true,
          show_classification_stamp: true,
          footer_text: "Confidencial — uso interno",
          show_generation_timestamp: true,
        },
        blocks: [
          { type: "alert_metadata", params: {} },
          { type: "evidence_grid", params: {} },
        ],
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "error";
      alert(`Error: ${msg}`);
    }
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">Plantillas de reporte</h1>
        <button
          type="button"
          onClick={handleCreate}
          disabled={createMutation.isPending}
          className="px-3 py-2 bg-blue-600 text-white rounded text-sm disabled:opacity-50"
        >
          + Nueva plantilla
        </button>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={includeInactive}
          onChange={(e) => setIncludeInactive(e.target.checked)}
        />
        Incluir plantillas inactivas
      </label>

      {query.isLoading && (
        <div className="text-sm text-gray-500">Cargando...</div>
      )}

      {!query.isLoading && templates.length === 0 && (
        <div className="text-sm text-gray-500 border rounded p-4">
          Sin plantillas. Crea una nueva.
        </div>
      )}

      {templates.length > 0 && (
        <table className="w-full text-sm">
          <thead className="bg-gray-100">
            <tr>
              <th className="text-left p-2">Nombre</th>
              <th className="text-left p-2">Código</th>
              <th className="text-left p-2">Versión</th>
              <th className="text-left p-2">Default</th>
              <th className="text-left p-2">Activa</th>
              <th className="text-left p-2">Tenant</th>
              <th className="text-left p-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((t) => (
              <tr key={t.id} className="border-b hover:bg-gray-50">
                <td className="p-2 font-medium">{t.name}</td>
                <td className="p-2 font-mono text-xs">{t.code}</td>
                <td className="p-2">v{t.current_version_number}</td>
                <td className="p-2">{t.is_default ? "⭐" : "—"}</td>
                <td className="p-2">{t.is_active ? "✅" : "❌"}</td>
                <td className="p-2 text-xs text-gray-600">
                  {t.tenant_id ? "tenant" : "global"}
                </td>
                <td className="p-2 space-x-2">
                  <Link
                    href={`/settings/alert-report-templates/${t.id}`}
                    className="text-blue-600 hover:underline text-xs"
                  >
                    Editar
                  </Link>
                  {!t.is_default && (
                    <button
                      type="button"
                      onClick={() => setDefaultMutation.mutate(t.id)}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      Marcar default
                    </button>
                  )}
                  {!t.is_default && (
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(
                          `¿Eliminar plantilla "${t.name}"?`,
                        )) {
                          deleteMutation.mutate(t.id);
                        }
                      }}
                      className="text-red-600 hover:underline text-xs"
                    >
                      Eliminar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
