"use client";

import { History, Pencil, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { TLPBadge } from "@/components/molecules/TLPBadge";
import { TaxonomyAuditLogModal } from "@/components/organisms/TaxonomyAuditLogModal";
import { TaxonomyDriftWarning } from "@/components/organisms/TaxonomyDriftWarning";
import {
  useSoftDeleteTaxonomy,
  useTaxonomyDetail,
} from "@/hooks/useSecurityTaxonomies";
import type { SecurityTaxonomy } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TaxonomyDetailPanelProps {
  taxonomyId: string | null;
  /** Map of id → taxonomy (typically the parent's flattened tree) for fork-source lookup. */
  taxonomyMap?: Map<string, SecurityTaxonomy>;
  onEdit?: (taxonomy: SecurityTaxonomy) => void;
  onDeleted?: () => void;
}

export function TaxonomyDetailPanel({
  taxonomyId,
  taxonomyMap,
  onEdit,
  onDeleted,
}: TaxonomyDetailPanelProps) {
  const { data: taxonomy, isLoading, error } = useTaxonomyDetail(taxonomyId);
  const [showAudit, setShowAudit] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteReason, setDeleteReason] = useState("");
  const deleteMutation = useSoftDeleteTaxonomy();

  const driftInfo = useMemo(() => {
    if (!taxonomy || !taxonomy.forked_from_global_id || !taxonomyMap) {
      return { isOutdated: false, globalUpdatedAt: null as string | null };
    }
    const source = taxonomyMap.get(taxonomy.forked_from_global_id);
    if (!source || !taxonomy.forked_from_global_at) {
      return { isOutdated: false, globalUpdatedAt: null as string | null };
    }
    const isOutdated =
      new Date(source.updated_at).getTime() >
      new Date(taxonomy.forked_from_global_at).getTime();
    return { isOutdated, globalUpdatedAt: source.updated_at };
  }, [taxonomy, taxonomyMap]);

  if (!taxonomyId) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-sm text-muted-foreground">
        Selecciona una taxonomía
      </div>
    );
  }

  if (isLoading) {
    return <div className="p-4 text-sm text-muted-foreground">Cargando...</div>;
  }
  if (error) {
    return (
      <div className="p-4 text-sm text-red-600">
        Error: {(error as Error).message}
      </div>
    );
  }
  if (!taxonomy) return null;

  async function handleSoftDelete() {
    if (!taxonomy) return;
    try {
      await deleteMutation.mutateAsync({
        id: taxonomy.id,
        reason: deleteReason.trim(),
      });
      setShowDeleteConfirm(false);
      setDeleteReason("");
      onDeleted?.();
    } catch (err) {
      // Mutation error surfaces via deleteMutation.error
      console.error(err);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <header className="border-b p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-mono text-muted-foreground">
              {taxonomy.tuic_code}
            </p>
            <h2 className="text-lg font-semibold">{taxonomy.name}</h2>
            {taxonomy.description ? (
              <p className="mt-1 text-sm text-muted-foreground">
                {taxonomy.description}
              </p>
            ) : null}
          </div>
          <div className="flex flex-col items-end gap-1">
            <TLPBadge tlp={taxonomy.tlp_default} />
            {taxonomy.tenant_id !== null ? (
              <span className="text-[10px] text-purple-700 dark:text-purple-400">
                tenant override
              </span>
            ) : (
              <span className="text-[10px] text-blue-700 dark:text-blue-400">
                global
              </span>
            )}
            {!taxonomy.is_active ? (
              <span className="text-[10px] text-red-700 dark:text-red-400">
                inactivo
              </span>
            ) : null}
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            onClick={() => onEdit?.(taxonomy)}
            className="inline-flex items-center gap-1 rounded border px-2 py-1 text-xs hover:bg-muted"
          >
            <Pencil className="h-3.5 w-3.5" /> Editar
          </button>
          <button
            type="button"
            onClick={() => setShowAudit(true)}
            className="inline-flex items-center gap-1 rounded border px-2 py-1 text-xs hover:bg-muted"
          >
            <History className="h-3.5 w-3.5" /> Audit Log
          </button>
          {taxonomy.is_active ? (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="inline-flex items-center gap-1 rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/40"
            >
              <Trash2 className="h-3.5 w-3.5" /> Soft-delete
            </button>
          ) : null}
        </div>
      </header>

      <div className="space-y-4 p-4">
        <TaxonomyDriftWarning
          taxonomy={taxonomy}
          isOutdated={driftInfo.isOutdated}
          globalUpdatedAt={driftInfo.globalUpdatedAt}
        />

        <DetailGrid taxonomy={taxonomy} />

        {showDeleteConfirm ? (
          <div className="rounded border border-red-300 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950/30">
            <p className="text-sm font-medium text-red-900 dark:text-red-200">
              Confirmar soft-delete
            </p>
            <p className="mt-1 text-xs text-red-800 dark:text-red-300">
              Esta taxonomía será marcada como inactiva. Casos abiertos o
              descendientes activos impedirán la operación.
            </p>
            <label className="mt-2 block text-xs">
              Motivo (requerido):
              <textarea
                value={deleteReason}
                onChange={(e) => setDeleteReason(e.target.value)}
                className="mt-1 block w-full rounded border bg-background p-1 text-sm"
                rows={2}
              />
            </label>
            {deleteMutation.error ? (
              <p className="mt-1 text-xs text-red-700">
                {(deleteMutation.error as Error).message}
              </p>
            ) : null}
            <div className="mt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setDeleteReason("");
                }}
                className="rounded border px-2 py-1 text-xs hover:bg-muted"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSoftDelete}
                disabled={!deleteReason.trim() || deleteMutation.isPending}
                className={cn(
                  "rounded bg-red-600 px-2 py-1 text-xs font-medium text-white",
                  "hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50",
                )}
              >
                {deleteMutation.isPending ? "Eliminando..." : "Confirmar"}
              </button>
            </div>
          </div>
        ) : null}
      </div>

      <TaxonomyAuditLogModal
        isOpen={showAudit}
        onClose={() => setShowAudit(false)}
        taxonomyId={taxonomy.id}
        taxonomyName={`${taxonomy.tuic_code} — ${taxonomy.name}`}
      />
    </div>
  );
}

// ── Detail field grid ───────────────────────────────────────────────────

function DetailGrid({ taxonomy }: { taxonomy: SecurityTaxonomy }) {
  const fields: Array<[string, React.ReactNode]> = [
    ["Tipo de caso", taxonomy.default_case_type],
    ["Requiere ticket", taxonomy.requires_ticket ? "Sí" : "No"],
    ["Modo de triage", taxonomy.triage_mode],
    ["Workflow delegado", taxonomy.delegated_workflow_id ?? "—"],
    ["Timeout triage (seg)", String(taxonomy.triage_timeout_seconds)],
    ["TLP default", taxonomy.tlp_default],
    ["Tipo de ataque", taxonomy.attack_type ?? "—"],
    ["Subtipo de ataque", taxonomy.attack_subtype ?? "—"],
    [
      "Impacto interno",
      taxonomy.internal_impact_context ?? "—",
    ],
    [
      "Impacto externo",
      taxonomy.external_impact_context ?? "—",
    ],
    ["Equipo responsable", taxonomy.managed_by_team_id ?? "—"],
    [
      "Fórmula priorización",
      taxonomy.prioritization_formula_id ?? "—",
    ],
    [
      "MITRE techniques",
      taxonomy.mitre_techniques.length > 0
        ? taxonomy.mitre_techniques.join(", ")
        : "—",
    ],
    ["Creado", new Date(taxonomy.created_at).toLocaleString()],
    ["Actualizado", new Date(taxonomy.updated_at).toLocaleString()],
  ];

  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Detalle
      </h3>
      <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
        {fields.map(([label, value]) => (
          <div key={label} className="flex items-baseline gap-2">
            <dt className="text-xs text-muted-foreground">{label}:</dt>
            <dd className="font-mono text-xs">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
