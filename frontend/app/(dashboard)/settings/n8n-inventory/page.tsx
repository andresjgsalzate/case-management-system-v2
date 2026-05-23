"use client";

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  CircleDashed,
  ExternalLink,
  GitMerge,
  Plus,
  Workflow,
  XCircle,
} from "lucide-react";

import { N8nWorkflowFormModal } from "@/components/organisms/N8nWorkflowFormModal";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import { useN8nInventory } from "@/hooks/useN8nInventory";
import type { N8nInventoryEntry, N8nInventoryStatus } from "@/lib/types";

type Filter = "all" | N8nInventoryStatus;

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "registered", label: "Registrados" },
  { value: "orphan_in_n8n", label: "Huérfanos en n8n" },
  { value: "orphan_in_cms", label: "Huérfanos en CMS" },
  { value: "unlinked", label: "Sin enlazar" },
];

const STATUS_META: Record<
  N8nInventoryStatus,
  { label: string; cls: string; Icon: typeof CheckCircle2 }
> = {
  registered: {
    label: "Registrado",
    cls: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200",
    Icon: CheckCircle2,
  },
  orphan_in_n8n: {
    label: "Huérfano (solo en n8n)",
    cls: "bg-amber-100 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200",
    Icon: CircleDashed,
  },
  orphan_in_cms: {
    label: "Huérfano (CMS apunta a n8n inexistente)",
    cls: "bg-rose-100 text-rose-900 dark:bg-rose-950/40 dark:text-rose-200",
    Icon: XCircle,
  },
  unlinked: {
    label: "Sin enlazar a n8n",
    cls: "bg-slate-200 text-slate-900 dark:bg-slate-700/40 dark:text-slate-200",
    Icon: GitMerge,
  },
};

export default function N8nInventoryPage() {
  usePermissionGuard("n8n_editor", "access");
  const qc = useQueryClient();
  const { data, isLoading, error } = useN8nInventory();
  const [filter, setFilter] = useState<Filter>("all");
  // When set, opens the workflow form pre-filled with this orphan's
  // n8n name + id so the operator only fills the curated metadata.
  const [orphanToRegister, setOrphanToRegister] = useState<{
    name?: string; n8n_workflow_id?: string;
  } | null>(null);

  const visible = useMemo(
    () => (data ?? []).filter((e) => filter === "all" || e.status === filter),
    [data, filter],
  );

  const counts = useMemo(() => {
    const c: Record<N8nInventoryStatus, number> = {
      registered: 0,
      orphan_in_n8n: 0,
      orphan_in_cms: 0,
      unlinked: 0,
    };
    (data ?? []).forEach((e) => {
      c[e.status]++;
    });
    return c;
  }, [data]);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link
          href="/settings"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-2"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Configuración
        </Link>
        <h1 className="text-xl font-semibold text-foreground">
          Inventario de workflows n8n
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5 max-w-2xl">
          Vista combinada de los workflows que existen en n8n y el catálogo
          de playbooks registrados en CMS. Permite detectar workflows
          huérfanos (en n8n sin registro CMS) o referencias rotas (CMS
          apunta a un workflow que ya no existe en n8n).
        </p>
      </div>

      {/* Summary chips */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {(["registered", "orphan_in_n8n", "orphan_in_cms", "unlinked"] as const).map(
          (s) => {
            const m = STATUS_META[s];
            return (
              <div
                key={s}
                className="rounded-lg border border-border bg-card p-3"
              >
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <m.Icon className="h-3.5 w-3.5" />
                  {m.label}
                </div>
                <p className="text-2xl font-semibold text-foreground mt-1">
                  {counts[s]}
                </p>
              </div>
            );
          },
        )}
      </div>

      {/* Filter pills */}
      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setFilter(f.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              filter === f.value
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:text-foreground"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        {isLoading ? (
          <p className="p-4 text-sm text-muted-foreground">
            Cargando inventario…
          </p>
        ) : error ? (
          <p className="p-4 text-sm text-destructive">
            Error al cargar el inventario.{" "}
            <span className="text-xs text-muted-foreground">
              Verifica que N8N_API_KEY esté en el .env del backend.
            </span>
          </p>
        ) : visible.length === 0 ? (
          <p className="p-8 text-sm text-muted-foreground text-center">
            Sin workflows en este filtro.
          </p>
        ) : (
          <InventoryTable
            entries={visible}
            onRegisterOrphan={(e) =>
              setOrphanToRegister({
                name: e.n8n_name ?? undefined,
                n8n_workflow_id: e.n8n_id ?? undefined,
              })
            }
          />
        )}
      </div>

      <N8nWorkflowFormModal
        isOpen={orphanToRegister !== null}
        prefill={orphanToRegister}
        onClose={() => {
          setOrphanToRegister(null);
          // Refresh inventory so the just-registered row flips to
          // "registered" without a manual reload.
          qc.invalidateQueries({ queryKey: ["n8n-inventory"] });
        }}
      />
    </div>
  );
}

function InventoryTable({
  entries, onRegisterOrphan,
}: {
  entries: N8nInventoryEntry[];
  onRegisterOrphan: (entry: N8nInventoryEntry) => void;
}) {
  return (
    <table className="w-full text-sm">
      <thead className="border-b bg-muted/40 text-left">
        <tr>
          <th className="px-3 py-2 font-medium">Nombre</th>
          <th className="px-3 py-2 font-medium">n8n ID</th>
          <th className="px-3 py-2 font-medium">Estado</th>
          <th className="px-3 py-2 font-medium">Catálogo CMS</th>
          <th className="px-3 py-2 font-medium" />
        </tr>
      </thead>
      <tbody>
        {entries.map((e, i) => {
          const meta = STATUS_META[e.status];
          const displayName = e.n8n_name ?? e.catalog?.name ?? "(sin nombre)";
          const n8nIdShort = e.n8n_id?.slice(0, 12) ?? "—";
          return (
            <tr
              key={`${e.n8n_id ?? "cms"}-${e.catalog?.id ?? i}`}
              className="border-b last:border-0 hover:bg-muted/30"
            >
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <Workflow
                    className={`h-4 w-4 shrink-0 ${
                      e.n8n_active === false
                        ? "text-muted-foreground"
                        : "text-purple-500"
                    }`}
                  />
                  <div>
                    <p className="font-medium">{displayName}</p>
                    {e.catalog?.description && (
                      <p className="text-xs text-muted-foreground line-clamp-1">
                        {e.catalog.description}
                      </p>
                    )}
                  </div>
                </div>
              </td>
              <td className="px-3 py-2">
                <code className="text-xs font-mono text-muted-foreground">
                  {n8nIdShort}
                </code>
                {e.n8n_active === false && (
                  <span className="ml-2 rounded bg-slate-200 px-1.5 py-0.5 text-[10px] dark:bg-slate-700/40">
                    inactive
                  </span>
                )}
              </td>
              <td className="px-3 py-2">
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${meta.cls}`}
                >
                  <meta.Icon className="h-3 w-3" />
                  {meta.label}
                </span>
              </td>
              <td className="px-3 py-2 text-xs">
                {e.catalog ? (
                  <Link
                    href="/settings/integrations"
                    className="text-primary hover:underline"
                  >
                    {e.catalog.name}
                  </Link>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
              <td className="px-3 py-2 text-right">
                <div className="inline-flex items-center gap-3">
                  {e.status === "orphan_in_n8n" && (
                    <button
                      type="button"
                      onClick={() => onRegisterOrphan(e)}
                      className="inline-flex items-center gap-1 rounded bg-primary px-2 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                      title="Registrar este workflow en el catálogo CMS"
                    >
                      <Plus className="h-3 w-3" />
                      Registrar
                    </button>
                  )}
                  {e.n8n_id && (
                    <Link
                      href={`/n8n#/workflow/${e.n8n_id}`}
                      className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                      title="Abrir en el editor"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      Abrir
                    </Link>
                  )}
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
