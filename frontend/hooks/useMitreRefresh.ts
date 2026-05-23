// Force a re-fetch of the MITRE catalog from upstream + invalidate
// the 24 h Redis cache. Gated server-side by security_taxonomies:manage_global.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type { ApiResponse } from "@/lib/types";

export interface MitreRefreshResult {
  count: number;
  ttl_seconds: number;
}

export function useMitreRefresh() {
  const qc = useQueryClient();
  return useMutation<MitreRefreshResult, Error, void>({
    mutationFn: async () => {
      const { data } = await apiClient.post<ApiResponse<MitreRefreshResult>>(
        "/mitre/refresh",
      );
      return data.data;
    },
    onSuccess: () => {
      // Drop any cached technique search results so the picker shows
      // the fresh catalog on the next open.
      qc.invalidateQueries({ queryKey: ["mitre-techniques"] });
    },
  });
}
