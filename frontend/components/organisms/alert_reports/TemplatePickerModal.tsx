"use client";

import { useEffect, useState } from "react";

import { useAlertReportTemplates } from "@/hooks/useAlertReportTemplates";
import type { AlertReportTemplate } from "@/lib/types";

interface Props {
  isOpen: boolean;
  caseId: string;
  onClose: () => void;
  onSelected: (templateId: string | null) => void;
  isGenerating?: boolean;
  error?: string | null;
}

export function TemplatePickerModal({
  isOpen, caseId, onClose, onSelected, isGenerating, error,
}: Props) {
  const query = useAlertReportTemplates();
  const templates = (query.data ?? []).filter((t) => t.is_active);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Pre-select the default template once the list arrives.
  useEffect(() => {
    if (selectedId !== null) return;
    const def = templates.find((t) => t.is_default);
    if (def) setSelectedId(def.id);
  }, [templates, selectedId]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="picker-title"
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    >
      <div className="bg-white rounded-lg p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 id="picker-title" className="text-xl font-semibold">
            Exportar PDF
          </h2>
          <button
            type="button"
            aria-label="Cerrar"
            onClick={onClose}
            disabled={isGenerating}
            className="text-2xl leading-none disabled:opacity-50"
          >
            ×
          </button>
        </div>

        <p className="text-sm text-gray-600 mb-3">
          Elige la plantilla con la que generar el reporte del caso{" "}
          <span className="font-mono">{caseId.slice(0, 8)}</span>.
        </p>

        {query.isLoading && (
          <div className="text-sm text-gray-500">Cargando plantillas...</div>
        )}

        {!query.isLoading && templates.length === 0 && (
          <div className="text-sm text-gray-500 border rounded p-3">
            Sin plantillas activas. Crea una en{" "}
            <span className="font-mono">/settings/alert-report-templates</span>.
          </div>
        )}

        {templates.length > 0 && (
          <fieldset
            className="space-y-2 mb-4"
            disabled={isGenerating}
          >
            <legend className="sr-only">Plantilla</legend>
            {templates.map((t) => (
              <TemplateRadio
                key={t.id}
                template={t}
                checked={selectedId === t.id}
                onChange={() => setSelectedId(t.id)}
              />
            ))}
          </fieldset>
        )}

        {error && (
          <div role="alert" className="text-sm text-red-600 mb-3">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isGenerating}
            className="px-4 py-2 border rounded"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => onSelected(selectedId)}
            disabled={!selectedId || isGenerating}
            className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
          >
            {isGenerating ? "Generando..." : "Generar PDF"}
          </button>
        </div>
      </div>
    </div>
  );
}

function TemplateRadio({
  template, checked, onChange,
}: {
  template: AlertReportTemplate;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label
      className={`block border rounded p-3 cursor-pointer ${
        checked ? "border-blue-500 bg-blue-50" : ""
      }`}
    >
      <div className="flex items-start gap-2">
        <input
          type="radio"
          name="template-picker"
          checked={checked}
          onChange={onChange}
          className="mt-1"
        />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">{template.name}</span>
            {template.is_default && (
              <span className="text-xs px-1.5 py-0.5 bg-yellow-100 border border-yellow-400 rounded">
                ⭐ Default
              </span>
            )}
            <span className="text-xs text-gray-500">
              v{template.current_version_number}
            </span>
          </div>
          {template.description && (
            <p className="text-xs text-gray-600 mt-1">
              {template.description}
            </p>
          )}
        </div>
      </div>
    </label>
  );
}
