"use client";

import { useParams, useRouter } from "next/navigation";

import { AlertReportTemplateEditor } from "@/components/organisms/alert_reports/AlertReportTemplateEditor";
import {
  useAlertReportTemplate,
  useUpdateAlertReportTemplate,
} from "@/hooks/useAlertReportTemplates";
import { useTemplateVersions } from "@/hooks/useTemplateVersions";

export default function AlertReportTemplateEditPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const templateId = params.id;

  const templateQuery = useAlertReportTemplate(templateId);
  const versionsQuery = useTemplateVersions(templateId);
  const updateMutation = useUpdateAlertReportTemplate();

  if (templateQuery.isLoading || versionsQuery.isLoading) {
    return (
      <div className="p-6 text-sm text-gray-500">
        Cargando plantilla...
      </div>
    );
  }
  if (templateQuery.error || !templateQuery.data) {
    return (
      <div className="p-6 text-red-600">
        Plantilla no encontrada.
      </div>
    );
  }

  const template = templateQuery.data;
  // Versions list is descending by version number; current version is the
  // first one whose id matches template.current_version_id.
  const versions = versionsQuery.data ?? [];
  const currentVersion = versions.find(
    (v) => v.id === template.current_version_id,
  ) ?? versions[0];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.push("/settings/alert-report-templates")}
          className="text-blue-600 hover:underline text-sm"
        >
          ← Volver
        </button>
        <h1 className="text-2xl font-semibold">
          {template.name}{" "}
          <span className="text-sm text-gray-500">
            v{template.current_version_number}
          </span>
        </h1>
      </div>

      <AlertReportTemplateEditor
        template={template}
        initialVersion={currentVersion}
        onSave={async (payload) => {
          await updateMutation.mutateAsync({
            id: template.id,
            body: payload,
          });
        }}
      />

      {versions.length > 0 && (
        <details className="mt-6">
          <summary className="cursor-pointer text-sm font-medium">
            Historial de versiones ({versions.length})
          </summary>
          <ul className="mt-2 space-y-1 text-sm">
            {versions.map((v) => (
              <li key={v.id} className="border rounded p-2">
                <div className="flex justify-between">
                  <span>
                    v{v.version} · {v.name_snapshot}
                  </span>
                  <span className="text-xs text-gray-500">
                    {new Date(v.created_at).toLocaleString()}
                  </span>
                </div>
                {v.change_summary && (
                  <div className="text-xs text-gray-600 mt-0.5">
                    {v.change_summary}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
