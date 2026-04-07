"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Shield } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { SearchBar } from "@/components/molecules/SearchBar";
import { Badge } from "@/components/atoms/Badge";
import { Spinner } from "@/components/atoms/Spinner";
import { formatRelative } from "@/lib/utils";
import type { AuditLog, ApiResponse } from "@/lib/types";

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

const ACTION_VARIANTS = {
  INSERT: "success",
  UPDATE: "warning",
  DELETE: "destructive",
} as const;

const ENTITY_TYPES = ["", "cases", "users", "kb_articles", "automation_rules"];

export default function AuditPage() {
  const [entityType, setEntityType] = useState("");
  const [search, setSearch] = useState("");

  const { data: logs = [], isLoading } = useAuditLogs(entityType || undefined);

  const filtered = search.trim()
    ? logs.filter(
        (l) =>
          l.entity_type.includes(search.toLowerCase()) ||
          l.entity_id.includes(search.toLowerCase()) ||
          l.actor_id?.includes(search.toLowerCase())
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
          placeholder="Buscar por entidad, ID o actor…"
          className="sm:w-72"
        />
        <select
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
          className="h-9 rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">Todas las entidades</option>
          {ENTITY_TYPES.filter(Boolean).map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        {isLoading && (
          <div className="flex justify-center py-16">
            <Spinner size="lg" />
          </div>
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
                {["Acción", "Entidad", "ID de entidad", "Actor", "Cambios", "Fecha"].map((col) => (
                  <th
                    key={col}
                    className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.map((log) => (
                <tr key={log.id} className="hover:bg-muted/40 transition-colors">
                  <td className="px-4 py-3">
                    <Badge variant={ACTION_VARIANTS[log.action] ?? "outline"}>
                      {log.action}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {log.entity_type}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground max-w-32 truncate">
                    {log.entity_id}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground max-w-28 truncate">
                    {log.actor_id ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground max-w-48">
                    {log.changes ? (
                      <span className="font-mono text-xs">
                        {Object.keys(log.changes).join(", ")}
                      </span>
                    ) : (
                      <span className="italic">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                    {formatRelative(log.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
