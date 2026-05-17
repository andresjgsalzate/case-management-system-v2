"use client";

import { useState } from "react";

import { AuditExplorerFiltersForm } from "@/components/organisms/audit_explorer/AuditExplorerFilters";
import { AuditExplorerResults } from "@/components/organisms/audit_explorer/AuditExplorerResults";
import {
  useAuditExplorer,
  useAuditExplorerCsvExport,
} from "@/hooks/useAuditExplorer";
import type { AuditExplorerFilters } from "@/lib/types";

export default function AuditExplorerPage() {
  const [filters, setFilters] = useState<AuditExplorerFilters | null>(null);
  const query = useAuditExplorer(filters);
  const csvExport = useAuditExplorerCsvExport();

  return (
    <div className="space-y-4 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold">Audit Explorer</h1>
        <p className="text-sm text-muted-foreground">
          Búsqueda cross-system de eventos: activity feed del caso, audit log
          general y eventos de integración entrantes.
        </p>
      </header>

      <AuditExplorerFiltersForm
        onSearch={setFilters}
        onExport={(f) => csvExport.mutate(f)}
      />

      <AuditExplorerResults
        result={query.data}
        isLoading={query.isLoading}
        error={query.error}
      />
    </div>
  );
}
