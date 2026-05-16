// Frontend hooks for Sub-spec 04 — Inbound Events log + replay.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  InboundEvent,
  InboundEventStatus,
} from "@/lib/types";

const BASE = "/inbound-events";

const keys = {
  all: ["inbound-events"] as const,
  lists: () => [...keys.all, "list"] as const,
  list: (filters: InboundEventsFilters) => [...keys.lists(), filters] as const,
  detail: (id: string) => [...keys.all, "detail", id] as const,
};

export interface InboundEventsFilters {
  status?: InboundEventStatus;
  source_id?: string;
  limit?: number;
}

// ── Reads ────────────────────────────────────────────────────────────────────

export function useInboundEvents(filters: InboundEventsFilters = {}) {
  return useQuery<InboundEvent[]>({
    queryKey: keys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      if (filters.source_id) params.set("source_id", filters.source_id);
      if (filters.limit) params.set("limit", String(filters.limit));
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<InboundEvent[]>>(
        `${BASE}${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
  });
}

export function useInboundEventDetail(id: string | null | undefined) {
  return useQuery<InboundEvent>({
    queryKey: keys.detail(id ?? ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<InboundEvent>>(
        `${BASE}/${id}`,
      );
      return data.data;
    },
  });
}

// ── Mutations ────────────────────────────────────────────────────────────────

export function useReplayInboundEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<ApiResponse<unknown>>(
        `${BASE}/${id}/replay`,
      );
      return data.data;
    },
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: keys.all });
      qc.invalidateQueries({ queryKey: keys.detail(id) });
    },
  });
}
