// Frontend hooks for Sub-spec 07 — hunt list with polling.
//
// Polls every 30s; once the operational_center SSE stream starts emitting
// `forensic.hunt_*` events (out of scope for this task), swap the polling
// for `useDashboardStream` subscription + `mutate` on those events.
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  ForensicHunt,
  ForensicHuntResult,
  ForensicHuntStatus,
} from "@/lib/types";

const BASE = "/forensic/hunts";

const keys = {
  all: ["forensic-hunts"] as const,
  lists: () => [...keys.all, "list"] as const,
  list: (filters: ForensicHuntFilters) =>
    [...keys.lists(), filters] as const,
  detail: (id: string) => [...keys.all, "detail", id] as const,
  results: (id: string) => [...keys.all, "results", id] as const,
};

export interface ForensicHuntFilters {
  case_id?: string;
  status?: ForensicHuntStatus;
  limit?: number;
}

export function useForensicHunts(filters: ForensicHuntFilters = {}) {
  return useQuery<ForensicHunt[]>({
    queryKey: keys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.case_id) params.set("case_id", filters.case_id);
      if (filters.status) params.set("status", filters.status);
      if (filters.limit) params.set("limit", String(filters.limit));
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<ForensicHunt[]>>(
        `${BASE}${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
    refetchInterval: 30_000,
  });
}

export function useForensicHuntDetail(id: string | null | undefined) {
  return useQuery<ForensicHunt>({
    queryKey: keys.detail(id ?? ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ForensicHunt>>(
        `${BASE}/${id}`,
      );
      return data.data;
    },
  });
}

export function useForensicHuntResults(huntId: string | null | undefined) {
  return useQuery<ForensicHuntResult[]>({
    queryKey: keys.results(huntId ?? ""),
    enabled: Boolean(huntId),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ForensicHuntResult[]>>(
        `${BASE}/${huntId}/results`,
      );
      return data.data;
    },
  });
}
