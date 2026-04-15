"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Shield, X, User, Box, Clock, Wifi, ChevronRight, History } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { SearchBar } from "@/components/molecules/SearchBar";
import { Badge } from "@/components/atoms/Badge";
import { Spinner } from "@/components/atoms/Spinner";
import { formatRelative } from "@/lib/utils";
import type { AuditLog, ApiResponse } from "@/lib/types";

// ── Hook ──────────────────────────────────────────────────────────────────────

function useAuditLogs(entityType?: string) {
  return useQuery({
    queryKey: ["audit", entityType],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<AuditLog[]>>("/audit", {
        params: entityType ? { entity_type: entityType, limit: 100 } : { limit: 100 },
      });
      return data.data ?? [];
    },
  });
}

function useTimelineLogs(entityType: string, entityId: string) {
  return useQuery({
    queryKey: ["audit-timeline", entityType, entityId],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<AuditLog[]>>(
        `/audit/timeline/${entityType}/${entityId}`
      );
      return data.data ?? [];
    },
    enabled: !!entityType && !!entityId,
  });
}

function useOperationLogs(correlationId: string | null | undefined) {
  return useQuery({
    queryKey: ["audit-operation", correlationId],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<AuditLog[]>>(
        `/audit/operation/${correlationId}`
      );
      return data.data ?? [];
    },
    enabled: !!correlationId,
  });
}

// ── Constants ─────────────────────────────────────────────────────────────────

const ACTION_VARIANTS = {
  INSERT: "success",
  UPDATE: "warning",
  DELETE: "destructive",
} as const;

const ACTION_LABELS: Record<string, string> = {
  INSERT: "Creación",
  UPDATE: "Edición",
  DELETE: "Eliminación",
};

const ENTITY_LABELS: Record<string, string> = {
  cases: "Casos",
  users: "Usuarios",
  kb_articles: "Artículos KB",
  automation_rules: "Reglas de automatización",
  dispositions: "Disposiciones",
  roles: "Roles",
  teams: "Equipos",
};

const ENTITY_TYPES = ["cases", "users", "kb_articles", "automation_rules", "dispositions", "roles", "teams"];

// Traducción de nombres de campos técnicos → español legible
const FIELD_LABELS: Record<string, string> = {
  // Cases
  title: "Título",
  description: "Descripción",
  complexity: "Complejidad",
  status_id: "Estado",
  priority_id: "Prioridad",
  assigned_to: "Asignado a",
  team_id: "Equipo",
  application_id: "Aplicación",
  origin_id: "Origen",
  is_archived: "Archivado",
  closed_at: "Cerrado el",
  case_number: "Número de caso",
  // Users
  full_name: "Nombre completo",
  email: "Correo electrónico",
  role_id: "Rol",
  is_active: "Activo",
  email_notifications: "Notificaciones por email",
  avatar_url: "Avatar",
  // Dispositions
  date: "Fecha",
  item_name: "Nombre del script",
  storage_path: "Ruta de almacenamiento",
  revision_number: "Número de revisión",
  observations: "Observaciones",
  category_id: "Categoría",
  // General
  name: "Nombre",
  content: "Contenido",
  is_closed: "Cerrado",
  color: "Color",
  level: "Nivel",
  sort_order: "Orden",
  usage_count: "Usos",
  created_at: "Creado el",
  updated_at: "Actualizado el",
  created_by: "Creado por",
  created_by_id: "Creado por",
  approved_by_id: "Aprobado por",
  tenant_id: "Organización",
};

// ── Timeline modal ────────────────────────────────────────────────────────────

function TimelineModal({
  entityType,
  entityId,
  entityLabel,
  onClose,
  onSelectLog,
}: {
  entityType: string;
  entityId: string;
  entityLabel?: string | null;
  onClose: () => void;
  onSelectLog: (log: AuditLog) => void;
}) {
  const { data: logs = [], isLoading } = useTimelineLogs(entityType, entityId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-semibold text-foreground">Línea de tiempo</p>
            <p className="text-xs text-muted-foreground">
              {entityLabel ?? entityId} · {ENTITY_LABELS[entityType] ?? entityType}
            </p>
          </div>
          <button type="button" onClick={onClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="overflow-y-auto flex-1 px-5 py-4">
          {isLoading && <div className="flex justify-center py-8"><Spinner size="lg" /></div>}
          {!isLoading && logs.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">Sin eventos registrados.</p>
          )}
          {!isLoading && logs.length > 0 && (
            <div className="relative">
              <div className="absolute left-[7px] top-2 bottom-2 w-px bg-border" />
              <div className="flex flex-col gap-0">
                {logs.map((log) => (
                  <button
                    key={log.id}
                    type="button"
                    onClick={() => onSelectLog(log)}
                    className="flex items-start gap-4 py-3 text-left hover:bg-muted/40 rounded-lg px-2 transition-colors group"
                  >
                    <div className={[
                      "mt-1 h-3.5 w-3.5 rounded-full border-2 shrink-0 z-10",
                      log.action === "INSERT" ? "bg-emerald-500 border-emerald-500" :
                      log.action === "DELETE" ? "bg-destructive border-destructive" :
                      "bg-amber-500 border-amber-500",
                    ].join(" ")} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge variant={ACTION_VARIANTS[log.action] ?? "outline"}>
                          {ACTION_LABELS[log.action] ?? log.action}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {log.actor_name ?? "Sistema"}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {new Date(log.created_at).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" })}
                      </p>
                      {log.request_path && (
                        <p className="text-xs font-mono text-muted-foreground/60 truncate mt-0.5">
                          {log.request_path}
                        </p>
                      )}
                    </div>
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40 group-hover:text-muted-foreground mt-1 shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Detail modal ──────────────────────────────────────────────────────────────

function DetailModal({ log, onClose }: { log: AuditLog; onClose: () => void }) {
  const allChanges = log.changes ?? {};
  const snapshot = allChanges._snapshot as Record<string, unknown> | undefined;
  const fieldChanges = Object.fromEntries(
    Object.entries(allChanges).filter(([k]) => k !== "_snapshot")
  ) as Record<string, { old: unknown; new: unknown }>;
  const hasFieldChanges = Object.keys(fieldChanges).length > 0;
  const hasSnapshot = !!snapshot && Object.keys(snapshot).length > 0;
  const hasBefore = !!log.before_snapshot && Object.keys(log.before_snapshot).length > 0;
  const [beforeOpen, setBeforeOpen] = useState(false);

  const { data: operationLogs = [] } = useOperationLogs(log.correlation_id);
  const relatedLogs = operationLogs.filter(l => l.id !== log.id);

  function renderValue(v: unknown): string {
    if (v === null || v === undefined) return "—";
    if (typeof v === "boolean") return v ? "Sí" : "No";
    if (typeof v === "object") return JSON.stringify(v, null, 2);
    return String(v);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <Badge variant={ACTION_VARIANTS[log.action] ?? "outline"}>
              {ACTION_LABELS[log.action] ?? log.action}
            </Badge>
            <span className="text-sm font-semibold text-foreground">
              {ENTITY_LABELS[log.entity_type] ?? log.entity_type}
            </span>
          </div>
          <button type="button" onClick={onClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-4 flex flex-col gap-4">

          {/* Metadata grid */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1 rounded-lg bg-muted/40 px-3 py-2.5">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Box className="h-3 w-3" />Entidad
              </div>
              <p className="text-xs font-medium text-foreground">
                {log.entity_label
                  ? log.entity_label
                  : log.action === "DELETE"
                    ? <span className="text-muted-foreground italic">Entidad eliminada</span>
                    : <span className="font-mono">{log.entity_id}</span>
                }
              </p>
              <p className="text-xs text-muted-foreground font-mono truncate">{log.entity_id}</p>
            </div>

            <div className="flex flex-col gap-1 rounded-lg bg-muted/40 px-3 py-2.5">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <User className="h-3 w-3" />Actor
              </div>
              <p className="text-xs font-medium text-foreground">{log.actor_name ?? "Sistema"}</p>
              {log.actor_id && (
                <p className="text-xs text-muted-foreground font-mono truncate">{log.actor_id}</p>
              )}
            </div>

            <div className="flex flex-col gap-1 rounded-lg bg-muted/40 px-3 py-2.5">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />Fecha
              </div>
              <p className="text-xs font-medium text-foreground">
                {new Date(log.created_at).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" })}
              </p>
              <p className="text-xs text-muted-foreground">{formatRelative(log.created_at)}</p>
            </div>

            {log.ip_address && (
              <div className="flex flex-col gap-1 rounded-lg bg-muted/40 px-3 py-2.5">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Wifi className="h-3 w-3" />IP
                </div>
                <p className="text-xs font-medium font-mono text-foreground">{log.ip_address}</p>
              </div>
            )}
          </div>

          {/* UPDATE: before/after table */}
          {hasFieldChanges && (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Campos modificados
              </p>
              <div className="rounded-lg border border-border overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border bg-muted/40">
                      <th className="px-3 py-2 text-left font-medium text-muted-foreground w-1/4">Campo</th>
                      <th className="px-3 py-2 text-left font-medium text-muted-foreground w-[37.5%]">Antes</th>
                      <th className="px-3 py-2 text-left font-medium text-muted-foreground w-[37.5%]">Después</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {Object.entries(fieldChanges).map(([field, { old: oldVal, new: newVal }]) => (
                      <tr key={field} className="hover:bg-muted/20">
                        <td className="px-3 py-2 font-medium text-foreground">
                          {FIELD_LABELS[field] ?? field}
                        </td>
                        <td className="px-3 py-2 text-destructive/80 break-all whitespace-pre-wrap max-w-[200px]">
                          {renderValue(oldVal)}
                        </td>
                        <td className="px-3 py-2 text-emerald-600 dark:text-emerald-400 break-all whitespace-pre-wrap max-w-[200px]">
                          {renderValue(newVal)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* INSERT / DELETE: full snapshot */}
          {hasSnapshot && (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {log.action === "INSERT" ? "Datos creados" : "Datos eliminados"}
              </p>
              <div className="rounded-lg border border-border overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border bg-muted/40">
                      <th className="px-3 py-2 text-left font-medium text-muted-foreground w-1/3">Campo</th>
                      <th className="px-3 py-2 text-left font-medium text-muted-foreground">Valor</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {Object.entries(snapshot)
                      .filter(([field]) => !["id", "tenant_id", "usage_count"].includes(field))
                      .map(([field, value]) => (
                        <tr key={field} className="hover:bg-muted/20">
                          <td className="px-3 py-2 font-medium text-foreground">
                            {FIELD_LABELS[field] ?? field}
                          </td>
                          <td className={[
                            "px-3 py-2 break-all whitespace-pre-wrap max-w-[300px]",
                            log.action === "DELETE"
                              ? "text-destructive/80"
                              : "text-emerald-600 dark:text-emerald-400",
                          ].join(" ")}>
                            {renderValue(value)}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Raw JSON fallback */}
          {!hasFieldChanges && !hasSnapshot && Object.keys(allChanges).length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Datos</p>
              <pre className="rounded-lg bg-muted/40 border border-border px-3 py-2.5 text-xs font-mono overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(allChanges, null, 2)}
              </pre>
            </div>
          )}

          {!hasFieldChanges && !hasSnapshot && Object.keys(allChanges).length === 0 && (
            <p className="text-xs text-muted-foreground italic">Sin datos adicionales registrados.</p>
          )}

          {/* UPDATE: full before state accordion */}
          {log.action === "UPDATE" && hasBefore && (
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => setBeforeOpen(o => !o)}
                className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors"
              >
                <ChevronRight className={["h-3.5 w-3.5 transition-transform", beforeOpen ? "rotate-90" : ""].join(" ")} />
                Estado anterior completo
              </button>
              {beforeOpen && (
                <div className="rounded-lg border border-border overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border bg-muted/40">
                        <th className="px-3 py-2 text-left font-medium text-muted-foreground w-1/3">Campo</th>
                        <th className="px-3 py-2 text-left font-medium text-muted-foreground">Valor anterior</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {Object.entries(log.before_snapshot!)
                        .filter(([field]) => !["id", "tenant_id", "usage_count"].includes(field))
                        .map(([field, value]) => (
                          <tr key={field} className="hover:bg-muted/20">
                            <td className="px-3 py-2 font-medium text-foreground">
                              {FIELD_LABELS[field] ?? field}
                            </td>
                            <td className="px-3 py-2 text-muted-foreground break-all whitespace-pre-wrap max-w-[300px]">
                              {renderValue(value)}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Correlated operation */}
          {relatedLogs.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Operación completa · {relatedLogs.length + 1} cambios en este request
              </p>
              <div className="rounded-lg border border-border overflow-hidden divide-y divide-border">
                {relatedLogs.map(related => (
                  <div key={related.id} className="flex items-center gap-3 px-3 py-2.5">
                    <Badge variant={ACTION_VARIANTS[related.action] ?? "outline"}>
                      {ACTION_LABELS[related.action] ?? related.action}
                    </Badge>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">
                        {ENTITY_LABELS[related.entity_type] ?? related.entity_type}
                        {related.entity_label ? ` · ${related.entity_label}` : ""}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
              {log.request_path && (
                <p className="text-xs font-mono text-muted-foreground/60">{log.request_path}</p>
              )}
              {log.user_agent && (
                <p className="text-xs text-muted-foreground/60 truncate">{log.user_agent}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AuditPage() {
  const [entityType, setEntityType] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<AuditLog | null>(null);
  const [timeline, setTimeline] = useState<{ entityType: string; entityId: string; entityLabel?: string | null } | null>(null);

  const { data: logs = [], isLoading } = useAuditLogs(entityType || undefined);

  const filtered = search.trim()
    ? logs.filter(l =>
        l.entity_type.includes(search.toLowerCase()) ||
        l.entity_id.includes(search.toLowerCase()) ||
        (l.entity_label ?? "").toLowerCase().includes(search.toLowerCase()) ||
        (l.actor_name ?? "").toLowerCase().includes(search.toLowerCase()) ||
        (l.actor_id ?? "").includes(search.toLowerCase())
      )
    : logs;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Auditoría</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Registro automático de todos los cambios en el sistema
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Buscar por entidad, nombre o actor…"
          className="sm:w-72"
        />
        <select
          value={entityType}
          onChange={e => setEntityType(e.target.value)}
          className="h-9 rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">Todas las entidades</option>
          {ENTITY_TYPES.map(t => (
            <option key={t} value={t}>{ENTITY_LABELS[t] ?? t}</option>
          ))}
        </select>
      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        {isLoading && (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        )}
        {!isLoading && filtered.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
            <Shield className="h-8 w-8 opacity-30" />
            <p className="text-sm">Sin registros de auditoría</p>
          </div>
        )}
        {!isLoading && filtered.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {["Acción", "Entidad", "Registro", "Actor", "Campos", "Fecha", "", ""].map((col, i) => (
                  <th
                    key={i}
                    className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.map(log => (
                <tr
                  key={log.id}
                  onClick={() => setSelected(log)}
                  className="hover:bg-muted/40 transition-colors cursor-pointer"
                >
                  <td className="px-4 py-3">
                    <Badge variant={ACTION_VARIANTS[log.action] ?? "outline"}>
                      {ACTION_LABELS[log.action] ?? log.action}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {ENTITY_LABELS[log.entity_type] ?? log.entity_type}
                  </td>
                  <td className="px-4 py-3 text-xs text-foreground max-w-[200px]">
                    {log.entity_label
                      ? <span className="truncate block">{log.entity_label}</span>
                      : <span className="font-mono text-muted-foreground truncate block">{log.entity_id}</span>
                    }
                  </td>
                  <td className="px-4 py-3 text-xs text-foreground whitespace-nowrap">
                    {log.actor_name ?? <span className="text-muted-foreground italic">Sistema</span>}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground max-w-[160px]">
                    {(() => {
                      if (!log.changes || Object.keys(log.changes).length === 0) return <span className="italic">—</span>;
                      const keys = Object.keys(log.changes).filter(k => k !== "_snapshot");
                      if (keys.length > 0) return <span className="truncate block">{keys.map(k => FIELD_LABELS[k] ?? k).join(", ")}</span>;
                      const snap = (log.changes as Record<string, unknown>)._snapshot as Record<string, unknown> | undefined;
                      const count = snap ? Object.keys(snap).length : 0;
                      return <span className="italic">{count} campo{count !== 1 ? "s" : ""}</span>;
                    })()}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                    {formatRelative(log.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={e => {
                        e.stopPropagation();
                        setTimeline({ entityType: log.entity_type, entityId: log.entity_id, entityLabel: log.entity_label });
                      }}
                      title="Ver línea de tiempo"
                      className="text-muted-foreground/40 hover:text-muted-foreground transition-colors p-0.5 rounded"
                    >
                      <History className="h-3.5 w-3.5" />
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <DetailModal log={selected} onClose={() => setSelected(null)} />
      )}
      {timeline && (
        <TimelineModal
          entityType={timeline.entityType}
          entityId={timeline.entityId}
          entityLabel={timeline.entityLabel}
          onClose={() => setTimeline(null)}
          onSelectLog={log => { setTimeline(null); setSelected(log); }}
        />
      )}
    </div>
  );
}
