"use client";

import { useState } from "react";

import type { AlertReportBlockType } from "@/lib/types";

const BLOCK_OPTIONS: { type: AlertReportBlockType; label: string }[] = [
  { type: "alert_metadata", label: "📋 Metadata de alerta" },
  { type: "priority_calculation", label: "📊 Cálculo de prioridad" },
  { type: "text", label: "📝 Texto / Markdown" },
  { type: "triage_analysis", label: "🔍 Análisis y triage" },
  { type: "evidence_grid", label: "🧾 Evidencia recolectada" },
  { type: "forensic_artifacts_list", label: "🔒 Hunts forenses" },
  { type: "behavior_relation", label: "🧠 Relación de comportamiento" },
  { type: "recommendations", label: "✅ Recomendaciones" },
  { type: "mitre_techniques", label: "⚔️ Técnicas MITRE" },
  { type: "iocs_table", label: "🚨 Tabla de IOCs" },
  { type: "signature", label: "✍️ Firmas" },
  { type: "page_break", label: "── Salto de página" },
  { type: "spacer", label: "↕️ Espaciador" },
  { type: "image", label: "🖼️ Imagen" },
];

interface Props {
  onAdd: (type: AlertReportBlockType) => void;
}

export function BlockPalette({ onAdd }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-3 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700"
      >
        + Agregar bloque ▼
      </button>
      {open && (
        <ul
          role="listbox"
          aria-label="Tipos de bloque"
          className="absolute z-10 mt-1 w-full max-h-80 overflow-y-auto bg-white border rounded shadow-lg"
        >
          {BLOCK_OPTIONS.map((opt) => (
            <li
              key={opt.type}
              role="option"
              aria-selected="false"
              tabIndex={0}
              className="px-3 py-2 cursor-pointer hover:bg-gray-100 text-sm"
              onClick={() => {
                onAdd(opt.type);
                setOpen(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onAdd(opt.type);
                  setOpen(false);
                }
              }}
            >
              <span className="font-mono text-xs text-gray-500">
                {opt.type}
              </span>
              <span className="ml-2">{opt.label}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
