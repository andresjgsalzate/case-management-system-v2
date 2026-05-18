"use client";

import { useState } from "react";

import {
  useAlertReportsForCase, useDeleteAlertReport,
} from "@/hooks/useAlertReports";
import {
  buildDownloadUrl, downloadAlertReportBlob,
} from "@/hooks/useGenerateReport";
import type { CaseGeneratedReport } from "@/lib/types";

import { IntegrityCheckBadge } from "./IntegrityCheckBadge";

interface Props {
  caseId: string;
  canDelete?: boolean;
}

export function ReportHistoryList({ caseId, canDelete = false }: Props) {
  const query = useAlertReportsForCase(caseId);
  const deleteMutation = useDeleteAlertReport();
  const reports = query.data ?? [];

  if (query.isLoading) {
    return (
      <div className="text-sm text-gray-500">Cargando reportes...</div>
    );
  }

  if (reports.length === 0) {
    return (
      <div className="text-sm text-gray-500 border rounded p-4">
        Sin reportes generados para este caso.
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {reports.map((r) => (
        <ReportRow
          key={r.id}
          report={r}
          canDelete={canDelete}
          onDelete={async (reason) => {
            await deleteMutation.mutateAsync({
              reportId: r.id, caseId, reason,
            });
          }}
        />
      ))}
    </ul>
  );
}

function ReportRow({
  report, canDelete, onDelete,
}: {
  report: CaseGeneratedReport;
  canDelete: boolean;
  onDelete: (reason: string) => Promise<void>;
}) {
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    const reason = window.prompt(
      "Razón para eliminar el reporte (requerido para auditoría):",
    );
    if (!reason || !reason.trim()) return;
    setDeleting(true);
    try {
      await onDelete(reason);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "error";
      window.alert(`Error: ${msg}`);
    } finally {
      setDeleting(false);
    }
  }

  function handleDownloadBlob() {
    downloadAlertReportBlob(report.id).then(({ blob, filename }) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60 * 1000);
    }).catch((e) => {
      window.alert(`Download error: ${e?.message ?? e}`);
    });
  }

  const generatedAt = new Date(report.generated_at).toLocaleString();
  const sizeKb = (report.pdf_size_bytes / 1024).toFixed(1);

  return (
    <li className="border rounded p-3">
      <div className="flex justify-between items-start mb-1">
        <div>
          <div className="text-sm">
            <strong>{generatedAt}</strong>{" "}
            <span className="text-xs text-gray-500">
              · v{report.template_version_number} ·{" "}
              {report.generated_via === "manual_ui" ? "manual" : "n8n"}
            </span>
          </div>
          <div className="text-xs text-gray-600">
            {sizeKb} KB ·{" "}
            <span className="font-mono">
              {report.pdf_sha256.slice(0, 12)}…
            </span>
          </div>
        </div>
        <div className="flex gap-3 items-center text-sm">
          <a
            href={buildDownloadUrl(report.id)}
            className="text-blue-600 hover:underline text-xs"
          >
            Descargar
          </a>
          <button
            type="button"
            onClick={handleDownloadBlob}
            className="text-blue-600 hover:underline text-xs"
          >
            Guardar como
          </button>
          <IntegrityCheckBadge reportId={report.id} />
          {canDelete && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="text-red-600 hover:underline text-xs disabled:opacity-50"
            >
              {deleting ? "Eliminando..." : "Eliminar"}
            </button>
          )}
        </div>
      </div>
    </li>
  );
}
