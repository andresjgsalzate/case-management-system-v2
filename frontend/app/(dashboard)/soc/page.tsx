"use client";

import { IntegrationHealthWidget } from "@/components/organisms/dashboard_soc/IntegrationHealthWidget";
import { KPIsWidget } from "@/components/organisms/dashboard_soc/KPIsWidget";
import { LiveEventsStreamWidget } from "@/components/organisms/dashboard_soc/LiveEventsStreamWidget";
import { PendingApprovalsWidget } from "@/components/organisms/dashboard_soc/PendingApprovalsWidget";
import { SeverityCountersWidget } from "@/components/organisms/dashboard_soc/SeverityCountersWidget";
import { useDashboardSummary } from "@/hooks/useDashboardSummary";

/** Centro Operacional SOC.
 *
 * Widget visibility is driven by the backend's permission-aware response —
 * each widget renders null when its summary field is null. No client-side
 * permission check needed; the backend is authoritative.
 */
export default function DashboardSOCPage() {
  const { data: summary, isLoading, error } = useDashboardSummary(24);

  if (isLoading) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        Cargando dashboard…
      </div>
    );
  }
  if (error) {
    return (
      <div className="p-6 text-sm text-red-600">
        Error al cargar dashboard. Revisa permisos / conectividad.
      </div>
    );
  }
  if (!summary) return null;

  return (
    <div className="space-y-4 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold">Centro Operacional SOC</h1>
        <p className="text-sm text-muted-foreground">
          Estado en vivo del SOC. Datos actualizados cada 30s + push vía SSE.
        </p>
      </header>

      <SeverityCountersWidget counters={summary.severity_counters} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PendingApprovalsWidget
          count={summary.pending_approvals_count}
          approvals={summary.pending_approvals}
        />
        <IntegrationHealthWidget sources={summary.integration_health} />
      </div>

      <KPIsWidget kpis={summary.kpis} />

      <LiveEventsStreamWidget />
    </div>
  );
}
