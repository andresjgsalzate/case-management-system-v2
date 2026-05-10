"use client";

import { useQuery } from "@tanstack/react-query";
import { Layers } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import type { ApiResponse, Case, CaseCustomValue } from "@/lib/types";

interface Props {
  caseId: string;
  /** Caso ya cargado en el padre — se usa para mostrar categoría + tipo */
  caseData?: Case;
}

export function CaseCustomValuesCard({ caseId, caseData }: Props) {
  const { data: customValues, isLoading } = useQuery({
    queryKey: ["case-custom-values", caseId],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<CaseCustomValue[]>>(
        `/cases/${caseId}/custom-values`,
      );
      return data.data ?? [];
    },
  });

  // Mostrar la tarjeta si hay categoría/tipo del catálogo o si hay valores custom.
  const hasCatalogInfo = !!caseData?.service_item_id;
  const hasCustomValues = customValues && customValues.length > 0;

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Spinner className="h-3 w-3" />
        Cargando información del servicio…
      </div>
    );
  }

  if (!hasCatalogInfo && !hasCustomValues) return null;

  return (
    <div className="rounded-lg border border-border bg-muted/20 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border">
        <Layers className="h-3.5 w-3.5 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-foreground">Información del servicio</h3>
      </div>
      <div className="divide-y divide-border">
        {/* Categoría y Tipo siempre primero */}
        {caseData?.service_category_name && (
          <FieldRow label="Categoría" value={caseData.service_category_name} />
        )}
        {caseData?.service_item_name && (
          <FieldRow label="Tipo de solicitud" value={caseData.service_item_name} />
        )}

        {/* Campos custom del catálogo */}
        {(customValues ?? []).map((v) => (
          <FieldRow key={v.field_id} label={v.label} value={formatValue(v)} />
        ))}
      </div>
    </div>
  );
}

function FieldRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-3 items-start px-4 py-2.5">
      <span className="text-xs font-medium text-muted-foreground mt-0.5">{label}</span>
      <span className="text-sm text-foreground whitespace-pre-wrap break-words">
        {value}
      </span>
    </div>
  );
}

function formatValue(v: CaseCustomValue): string {
  if (v.value === null || v.value === "") return "—";

  if (v.field_type === "checkbox") {
    return v.value === "true" || v.value === "1" ? "Sí" : "No";
  }

  // Para tipos con options: resolver value(s) interno(s) → label visible(s)
  const labelFor = (raw: string): string => {
    const opt = v.options?.find((o) => o.value === raw);
    return opt?.label ?? raw;
  };

  if (v.field_type === "select" || v.field_type === "radio") {
    return labelFor(v.value);
  }

  if (v.field_type === "multiselect") {
    let arr: string[];
    try {
      const parsed = JSON.parse(v.value);
      arr = Array.isArray(parsed) ? parsed : [v.value];
    } catch {
      arr = v.value.split(",").map((s) => s.trim());
    }
    return arr.map(labelFor).join(", ");
  }

  return v.value;
}
