// Discover webhook entry points for an n8n workflow so the
// "Registrar orphan" flow can pre-fill workflow_url without forcing
// the operator to copy/paste from the n8n editor. Returns empty list
// when the workflow has no webhook trigger (schedule/manual/etc.).
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type { ApiResponse } from "@/lib/types";

export interface N8nWorkflowWebhook {
  path: string;
  url: string;
  http_method: string;
  node_name: string;
  node_type: string;
}

export function useN8nWorkflowWebhooks(n8nWorkflowId: string | null) {
  return useQuery<N8nWorkflowWebhook[]>({
    queryKey: ["n8n-workflow-webhooks", n8nWorkflowId],
    enabled: !!n8nWorkflowId,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<N8nWorkflowWebhook[]>>(
        `/n8n-inventory/workflows/${n8nWorkflowId}/webhooks`,
      );
      return data.data;
    },
  });
}
