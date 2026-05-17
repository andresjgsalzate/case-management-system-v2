// Frontend hook for Sub-spec 06 — Dashboard summary aggregator.
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type { ApiResponse, SocDashboardSummary } from "@/lib/types";

const BASE = "/operational/dashboard/summary";

export function useSocDashboardSummary(periodHours: number = 24) {
  return useQuery<SocDashboardSummary>({
    queryKey: ["dashboard-summary", periodHours],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<SocDashboardSummary>>(
        `${BASE}?period_hours=${periodHours}`,
      );
      return data.data;
    },
    // Auto-refresh every 30s in addition to the SSE stream — covers the
    // case where SSE is temporarily disconnected.
    refetchInterval: 30_000,
  });
}
