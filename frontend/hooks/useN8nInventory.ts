// React Query hook for the n8n inventory endpoint.
// Returns a unified list mixing live n8n workflows + CMS catalog rows
// with a status flag per entry. See `backend/n8n_inventory/use_cases`
// for the merge logic.
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type { ApiResponse, N8nInventoryEntry } from "@/lib/types";

export function useN8nInventory() {
  return useQuery<N8nInventoryEntry[]>({
    queryKey: ["n8n-inventory"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<N8nInventoryEntry[]>>(
        "/n8n-inventory/workflows",
      );
      return data.data;
    },
    // n8n inventory drifts slowly; cache 30 s + refetch on focus is
    // plenty for an admin audit view.
    staleTime: 30_000,
  });
}
