"use client";

import { useState } from "react";

import { useGenerateAlertReport } from "@/hooks/useGenerateReport";
import { useHasPermission } from "@/hooks/useHasPermission";

import { ReportHistoryList } from "./ReportHistoryList";
import { TemplatePickerModal } from "./TemplatePickerModal";

interface Props {
  caseId: string;
}

export function AlertReportTab({ caseId }: Props) {
  const canGenerate = useHasPermission("alert_reports", "generate");
  const canDelete = useHasPermission("alert_reports", "delete");

  const generateMutation = useGenerateAlertReport();
  const [pickerOpen, setPickerOpen] = useState(false);

  async function handleSelected(templateId: string | null) {
    try {
      await generateMutation.mutateAsync({
        caseId,
        body: { template_id: templateId },
      });
      setPickerOpen(false);
    } catch {
      // error surfaces via mutation.error; keep modal open so the user
      // sees the message
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between rounded border bg-card p-3">
        <div>
          <h3 className="text-sm font-semibold">Reportes de alerta</h3>
          <p className="text-xs text-muted-foreground">
            Reportes PDF generados a partir de plantillas. Cada reporte
            mantiene su snapshot inmutable y un hash SHA-256 para verificar
            integridad.
          </p>
        </div>
        {canGenerate && (
          <button
            type="button"
            onClick={() => setPickerOpen(true)}
            disabled={generateMutation.isPending}
            className="inline-flex items-center gap-1 rounded border bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {generateMutation.isPending
              ? "Generando..."
              : "+ Exportar PDF"}
          </button>
        )}
      </header>

      <section aria-labelledby="reports-list-title">
        <h4
          id="reports-list-title"
          className="text-sm font-medium mb-2"
        >
          Historial
        </h4>
        <ReportHistoryList caseId={caseId} canDelete={canDelete} />
      </section>

      <TemplatePickerModal
        isOpen={pickerOpen}
        caseId={caseId}
        onClose={() => setPickerOpen(false)}
        onSelected={handleSelected}
        isGenerating={generateMutation.isPending}
        error={generateMutation.error?.message ?? null}
      />
    </div>
  );
}
