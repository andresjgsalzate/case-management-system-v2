// MITRE ATT&CK technique lookup -- backed by a static snapshot the
// backend serves in-memory. Search is cheap; cache 5 min since the
// dataset only refreshes on backend redeploy.
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type { ApiResponse } from "@/lib/types";

export interface MitreTechnique {
  id: string;
  name: string;
  tactics: string[];
  is_subtechnique: boolean;
  // Populated for sub-techniques (e.g. T1003.001 -> parent T1003
  // "OS Credential Dumping"). Null for top-level techniques.
  parent_id: string | null;
  parent_name: string | null;
}

export function useMitreTechniqueSearch(query: string, enabled = true) {
  return useQuery<MitreTechnique[]>({
    queryKey: ["mitre-techniques", "search", query],
    enabled,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<MitreTechnique[]>>(
        `/mitre/techniques?q=${encodeURIComponent(query)}&limit=50`,
      );
      return data.data;
    },
  });
}

export function useMitreTechniquesByIds(ids: string[]) {
  return useQuery<Record<string, MitreTechnique>>({
    queryKey: ["mitre-techniques", "by-ids", ids.sort().join(",")],
    enabled: ids.length > 0,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      // The lookup endpoint is per-id; for handful of chips this is
      // cheaper than fetching the whole catalog client-side.
      const entries = await Promise.all(
        ids.map(async (id) => {
          try {
            const { data } = await apiClient.get<ApiResponse<MitreTechnique>>(
              `/mitre/techniques/${encodeURIComponent(id)}`,
            );
            return [id, data.data] as const;
          } catch {
            return [id, null] as const;
          }
        }),
      );
      const out: Record<string, MitreTechnique> = {};
      for (const [id, t] of entries) if (t) out[id] = t;
      return out;
    },
  });
}
