"use client";

import { FileText } from "lucide-react";

interface Props {
  caseId: string;
}

/** Alert Report — Phase 1 view-only.
 *
 * The full report generator with PDF export lives in Sub-spec 08. For now
 * we display the case data in the standard report layout so operators
 * can preview what the eventual PDF will contain.
 */
export function AlertReportTab({ caseId }: Props) {
  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between rounded border bg-card p-3">
        <div>
          <h3 className="text-sm font-semibold">Reporte de alerta (preview)</h3>
          <p className="text-xs text-muted-foreground">
            Vista previa de los datos que compondrán el PDF. La generación
            completa con plantilla + PDF export llega en Sub-spec 08.
          </p>
        </div>
        <button
          type="button"
          disabled
          title="Exportación PDF disponible en Sub-spec 08"
          className="inline-flex items-center gap-1 rounded border bg-muted px-3 py-1.5 text-xs text-muted-foreground"
        >
          <FileText className="h-3 w-3" /> Exportar PDF
        </button>
      </header>

      <Section title="Información de la alerta">
        <p className="text-xs text-muted-foreground">
          Caso <span className="font-mono">{caseId}</span> — los campos del
          reporte (taxonomía, prioridad, fuente, fechas) se rellenarán
          automáticamente desde el modelo del caso cuando Sub-spec 08
          implemente el composer de plantillas.
        </p>
      </Section>

      <Section title="Análisis y triage">
        <p className="text-xs text-muted-foreground">
          Las notas con prefijo <code className="font-mono">[triage]</code>{" "}
          de la pestaña Notas se incluirán aquí. (Persistencia editable de
          esta sección llega con el composer.)
        </p>
      </Section>

      <Section title="Evidencia">
        <p className="text-xs text-muted-foreground">
          Lista de attachments + artefactos forenses (sub-tab anterior) se
          enumerará aquí.
        </p>
      </Section>

      <Section title="Recomendaciones">
        <p className="text-xs text-muted-foreground">
          Sección editable como nota persistida; pendiente del composer.
        </p>
      </Section>
    </div>
  );
}

function Section({
  title, children,
}: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded border bg-card p-3">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h4>
      <div>{children}</div>
    </section>
  );
}
