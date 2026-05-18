"use client";

import { useState } from "react";

import { apiClient } from "@/lib/apiClient";
import type {
  AlertReportBlock,
  AlertReportBlockType,
  AlertReportTemplate,
  AlertReportTemplateVersion,
} from "@/lib/types";

import { BlockPalette } from "./BlockPalette";

interface SavePayload {
  name: string;
  blocks: AlertReportBlock[];
  header_config: Record<string, unknown>;
  footer_config: Record<string, unknown>;
  change_summary: string;
}

interface Props {
  template?: AlertReportTemplate;
  initialVersion?: AlertReportTemplateVersion;
  onSave: (payload: SavePayload) => Promise<void> | void;
}

const DEFAULT_HEADER: Record<string, unknown> = {
  show_logo: true,
  show_classification: true,
  show_case_metadata_table: true,
  title_template: "DESCRIPCIÓN GENERAL DE LA GESTIÓN DE LA ALERTA",
};
const DEFAULT_FOOTER: Record<string, unknown> = {
  show_page_numbers: true,
  show_classification_stamp: true,
  footer_text: "Confidencial — uso interno",
  show_generation_timestamp: true,
};

export function AlertReportTemplateEditor({
  template, initialVersion, onSave,
}: Props) {
  const [name, setName] = useState(template?.name ?? "");
  const [blocks, setBlocks] = useState<AlertReportBlock[]>(
    initialVersion?.blocks ?? [],
  );
  const [headerConfig, setHeaderConfig] = useState(
    initialVersion?.header_config ?? DEFAULT_HEADER,
  );
  const [footerConfig, setFooterConfig] = useState(
    initialVersion?.footer_config ?? DEFAULT_FOOTER,
  );
  const [changeSummary, setChangeSummary] = useState("");
  const [sampleCaseId, setSampleCaseId] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  function addBlock(type: AlertReportBlockType) {
    setBlocks((prev) => [...prev, { type, params: {} }]);
  }
  function removeBlock(idx: number) {
    setBlocks((prev) => prev.filter((_, i) => i !== idx));
  }
  function moveBlock(idx: number, dir: -1 | 1) {
    setBlocks((prev) => {
      const next = [...prev];
      const target = idx + dir;
      if (target < 0 || target >= next.length) return prev;
      [next[idx], next[target]] = [next[target], next[idx]];
      return next;
    });
  }
  function updateBlockParams(idx: number, paramsJson: string) {
    setBlocks((prev) =>
      prev.map((b, i) => {
        if (i !== idx) return b;
        try {
          const parsed = JSON.parse(paramsJson || "{}");
          return { ...b, params: parsed };
        } catch {
          return b;  // keep prior params if user typed invalid JSON
        }
      }),
    );
  }

  async function handleSave() {
    if (!name.trim()) {
      setSaveError("Nombre requerido");
      return;
    }
    setSaveError(null);
    setIsSaving(true);
    try {
      await onSave({
        name,
        blocks,
        header_config: headerConfig,
        footer_config: footerConfig,
        change_summary: changeSummary,
      });
      setChangeSummary("");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Error desconocido";
      setSaveError(msg);
    } finally {
      setIsSaving(false);
    }
  }

  async function handlePreview() {
    if (!template?.id) {
      setPreviewError("Guarda primero la plantilla");
      return;
    }
    if (!sampleCaseId.trim()) {
      setPreviewError("Ingresa un case_id de ejemplo");
      return;
    }
    setPreviewError(null);
    setIsPreviewing(true);
    try {
      const response = await apiClient.post(
        `/alert-report-templates/${template.id}/preview`,
        {
          sample_case_id: sampleCaseId,
          blocks_override: blocks,
          header_override: headerConfig,
          footer_override: footerConfig,
        },
        { responseType: "blob" },
      );
      const url = URL.createObjectURL(response.data as Blob);
      window.open(url, "_blank", "noopener");
      // Schedule URL cleanup once browser is done with it (5 min margin)
      setTimeout(() => URL.revokeObjectURL(url), 5 * 60 * 1000);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Error desconocido";
      setPreviewError(msg);
    } finally {
      setIsPreviewing(false);
    }
  }

  return (
    <div className="space-y-4">
      <header className="space-y-2">
        <label className="block text-sm font-medium" htmlFor="tpl-name">
          Nombre
        </label>
        <input
          id="tpl-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full border rounded px-3 py-2"
          placeholder="Reporte SOC estándar"
        />
      </header>

      <div className="grid grid-cols-[280px_1fr] gap-4">
        <aside className="space-y-3">
          <BlockPalette onAdd={addBlock} />
          <div className="text-xs text-gray-600 p-2 border rounded bg-gray-50">
            <strong>Bloques:</strong> {blocks.length}
            <br />
            <span>
              Usa los botones ▲ ▼ para reordenar.
              JSON inválido en params se ignora hasta que sea válido.
            </span>
          </div>
        </aside>

        <main className="space-y-4">
          <section aria-labelledby="header-config-title" className="border rounded p-3">
            <h3 id="header-config-title" className="font-semibold mb-2">
              Encabezado (header_config)
            </h3>
            <textarea
              value={JSON.stringify(headerConfig, null, 2)}
              onChange={(e) => {
                try {
                  setHeaderConfig(JSON.parse(e.target.value || "{}"));
                } catch {
                  /* keep previous on invalid JSON */
                }
              }}
              rows={6}
              className="w-full border rounded px-2 py-1 font-mono text-xs"
            />
          </section>

          <section aria-labelledby="blocks-title">
            <h3 id="blocks-title" className="font-semibold mb-2">
              Bloques ({blocks.length})
            </h3>
            {blocks.length === 0 ? (
              <p className="text-sm text-gray-500 p-3 border rounded">
                Sin bloques. Usa &quot;+ Agregar bloque&quot; para empezar.
              </p>
            ) : (
              <ol className="space-y-2">
                {blocks.map((b, i) => (
                  <li
                    key={`${b.type}-${i}`}
                    className="border rounded p-3 bg-white"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-sm font-medium">
                        {i + 1}. {b.type}
                      </span>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          aria-label="Mover arriba"
                          disabled={i === 0}
                          onClick={() => moveBlock(i, -1)}
                          className="px-2 py-1 border rounded text-xs disabled:opacity-30"
                        >
                          ▲
                        </button>
                        <button
                          type="button"
                          aria-label="Mover abajo"
                          disabled={i === blocks.length - 1}
                          onClick={() => moveBlock(i, 1)}
                          className="px-2 py-1 border rounded text-xs disabled:opacity-30"
                        >
                          ▼
                        </button>
                        <button
                          type="button"
                          aria-label="Eliminar"
                          onClick={() => removeBlock(i)}
                          className="px-2 py-1 border rounded text-xs text-red-600"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                    <label className="block text-xs text-gray-600 mb-1">
                      params (JSON)
                    </label>
                    <textarea
                      defaultValue={JSON.stringify(b.params, null, 2)}
                      onChange={(e) => updateBlockParams(i, e.target.value)}
                      rows={4}
                      className="w-full border rounded px-2 py-1 font-mono text-xs"
                    />
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section aria-labelledby="footer-config-title" className="border rounded p-3">
            <h3 id="footer-config-title" className="font-semibold mb-2">
              Pie de página (footer_config)
            </h3>
            <textarea
              value={JSON.stringify(footerConfig, null, 2)}
              onChange={(e) => {
                try {
                  setFooterConfig(JSON.parse(e.target.value || "{}"));
                } catch {
                  /* keep previous on invalid JSON */
                }
              }}
              rows={6}
              className="w-full border rounded px-2 py-1 font-mono text-xs"
            />
          </section>

          <section aria-labelledby="change-summary-title" className="border rounded p-3">
            <label
              id="change-summary-title"
              className="block font-semibold mb-2"
              htmlFor="change-summary"
            >
              Resumen de cambios (opcional)
            </label>
            <input
              id="change-summary"
              type="text"
              value={changeSummary}
              onChange={(e) => setChangeSummary(e.target.value)}
              placeholder="Agregada sección de IOCs"
              className="w-full border rounded px-2 py-1"
            />
          </section>

          {saveError && (
            <div role="alert" className="text-sm text-red-600">
              {saveError}
            </div>
          )}

          <div className="flex flex-wrap gap-3 items-center">
            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving}
              className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
            >
              {isSaving ? "Guardando..." : "Guardar"}
            </button>

            {template?.id && (
              <>
                <input
                  type="text"
                  value={sampleCaseId}
                  onChange={(e) => setSampleCaseId(e.target.value)}
                  placeholder="case_id de muestra"
                  className="border rounded px-2 py-1 text-sm"
                />
                <button
                  type="button"
                  onClick={handlePreview}
                  disabled={isPreviewing || !sampleCaseId}
                  className="px-3 py-2 border rounded text-sm disabled:opacity-50"
                >
                  {isPreviewing ? "Generando..." : "Vista previa"}
                </button>
              </>
            )}
          </div>

          {previewError && (
            <div role="alert" className="text-sm text-red-600">
              {previewError}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
