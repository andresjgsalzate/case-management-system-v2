// Frontend hook for Sub-spec 07 — Velociraptor client (host) listing.
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type { ApiResponse, VeloClient } from "@/lib/types";

const BASE = "/forensic/clients";

const keys = {
  all: ["forensic-clients"] as const,
  list: (search: string, limit: number) =>
    [...keys.all, "list", { search, limit }] as const,
};

export function useVeloClients(search = "", limit = 100) {
  return useQuery<VeloClient[]>({
    queryKey: keys.list(search, limit),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (limit !== 100) params.set("limit", String(limit));
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<VeloClient[]>>(
        `${BASE}${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
  });
}
