// List teams in the current tenant. Cached 5 min -- team membership
// is operational config that changes infrequently relative to a UI session.
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type { ApiResponse, Team } from "@/lib/types";

export function useTeams() {
  return useQuery<Team[]>({
    queryKey: ["teams", "list"],
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Team[]>>("/teams");
      return data.data;
    },
  });
}
