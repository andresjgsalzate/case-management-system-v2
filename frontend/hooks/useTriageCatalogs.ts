// Catalogs that power the triage form dropdowns. Backend doesn't yet
// expose dedicated list endpoints for these (Phase 5 will add full
// CRUD UI). For now we hit /security-taxonomies (already exposed) for
// sub-taxonomy options, and inline-fetch the two triage_* catalogs
// via the raw apiClient until the proper endpoints land.
//
// TEMP: tool_types + tool_actions are read with custom helper queries
// against an admin-only catalog endpoint we'll add in Phase 5. Until
// then, they're empty arrays -- the form falls back to free-text or
// disabled dropdowns.
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  TriageToolAction,
  TriageToolType,
} from "@/lib/types";

export function useTriageToolTypes() {
  return useQuery<TriageToolType[]>({
    queryKey: ["triage-tool-types"],
    staleTime: 10 * 60 * 1000,
    queryFn: async () => {
      try {
        const { data } = await apiClient.get<ApiResponse<TriageToolType[]>>(
          "/triage-catalogs/tool-types",
        );
        return data.data;
      } catch {
        // Endpoint not implemented yet (Phase 5). Return empty so the
        // form still renders without crashing.
        return [];
      }
    },
  });
}

export function useTriageToolActions() {
  return useQuery<TriageToolAction[]>({
    queryKey: ["triage-tool-actions"],
    staleTime: 10 * 60 * 1000,
    queryFn: async () => {
      try {
        const { data } = await apiClient.get<ApiResponse<TriageToolAction[]>>(
          "/triage-catalogs/tool-actions",
        );
        return data.data;
      } catch {
        return [];
      }
    },
  });
}
