// Frontend hooks for Sub-spec 07 — Velociraptor artifact catalog.
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type { ApiResponse, ForensicArtifact } from "@/lib/types";

const BASE = "/forensic/artifacts";

const keys = {
  all: ["forensic-artifacts"] as const,
  lists: () => [...keys.all, "list"] as const,
  list: (filters: ForensicArtifactFilters) =>
    [...keys.lists(), filters] as const,
};

export interface ForensicArtifactFilters {
  featured_only?: boolean;
  category?: string;
  os?: string;
  search?: string;
  include_destructive?: boolean;
}

export function useForensicArtifacts(filters: ForensicArtifactFilters = {}) {
  return useQuery<ForensicArtifact[]>({
    queryKey: keys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.featured_only) params.set("featured_only", "true");
      if (filters.category) params.set("category", filters.category);
      if (filters.os) params.set("os", filters.os);
      if (filters.search) params.set("search", filters.search);
      if (filters.include_destructive) {
        params.set("include_destructive", "true");
      }
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<ForensicArtifact[]>>(
        `${BASE}${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
  });
}
