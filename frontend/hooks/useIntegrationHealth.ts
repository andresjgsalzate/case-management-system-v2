// Frontend hooks for Sub-spec 06 — Integration health monitor.
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  IntegrationHealthHistoryPoint,
  IntegrationHealthSummary,
} from "@/lib/types";

const BASE = "/operational/integration-health";

export function useIntegrationHealth() {
  return useQuery<IntegrationHealthSummary[]>({
    queryKey: ["integration-health", "list"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<IntegrationHealthSummary[]>>(BASE);
      return data.data;
    },
    refetchInterval: 60_000,  // matches backend snapshot cadence
  });
}

export function useIntegrationHealthHistory(
  sourceId: string | null | undefined,
  hours: number = 6,
) {
  return useQuery<IntegrationHealthHistoryPoint[]>({
    queryKey: ["integration-health", "history", sourceId, hours],
    enabled: Boolean(sourceId),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<IntegrationHealthHistoryPoint[]>>(
        `${BASE}/${sourceId}/history?hours=${hours}`,
      );
      return data.data;
    },
  });
}
