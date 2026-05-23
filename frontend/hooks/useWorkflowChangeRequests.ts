// React Query hooks for the Workflow Change Request tracker (sub-spec 09 §3.9).
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  CreateWCRPayload,
  ImplementWCRPayload,
  UpdateWCRStatusPayload,
  WCRStatus,
  WorkflowChangeRequest,
} from "@/lib/types";

const BASE = "/workflow-change-requests";

const keys = {
  all: ["workflow-change-requests"] as const,
  lists: () => [...keys.all, "list"] as const,
  list: (filters: WCRListFilters) => [...keys.lists(), filters] as const,
  detail: (id: string) => [...keys.all, "detail", id] as const,
  pendingCount: () => [...keys.all, "pending-count"] as const,
};

export interface WCRListFilters {
  status?: WCRStatus;
  requester_id?: string;
}

export function useWCRs(filters: WCRListFilters = {}) {
  return useQuery<WorkflowChangeRequest[]>({
    queryKey: keys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      if (filters.requester_id) params.set("requester_id", filters.requester_id);
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<WorkflowChangeRequest[]>>(
        `${BASE}${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
  });
}

export function useWCR(id: string | null | undefined) {
  return useQuery<WorkflowChangeRequest>({
    queryKey: keys.detail(id ?? ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<WorkflowChangeRequest>>(
        `${BASE}/${id}`,
      );
      return data.data;
    },
  });
}

export function useCreateWCR() {
  const qc = useQueryClient();
  return useMutation<WorkflowChangeRequest, Error, CreateWCRPayload>({
    mutationFn: async (body) => {
      const { data } = await apiClient.post<ApiResponse<WorkflowChangeRequest>>(
        BASE,
        body,
      );
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

interface UpdateStatusArgs {
  id: string;
  body: UpdateWCRStatusPayload;
}

export function useUpdateWCRStatus() {
  const qc = useQueryClient();
  return useMutation<WorkflowChangeRequest, Error, UpdateStatusArgs>({
    mutationFn: async ({ id, body }) => {
      const { data } = await apiClient.patch<ApiResponse<WorkflowChangeRequest>>(
        `${BASE}/${id}/status`,
        body,
      );
      return data.data;
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: keys.all });
      qc.invalidateQueries({ queryKey: keys.detail(vars.id) });
    },
  });
}

interface ImplementArgs {
  id: string;
  body: ImplementWCRPayload;
}

export function useImplementWCR() {
  const qc = useQueryClient();
  return useMutation<WorkflowChangeRequest, Error, ImplementArgs>({
    mutationFn: async ({ id, body }) => {
      const { data } = await apiClient.post<ApiResponse<WorkflowChangeRequest>>(
        `${BASE}/${id}/implement`,
        body,
      );
      return data.data;
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: keys.all });
      qc.invalidateQueries({ queryKey: keys.detail(vars.id) });
    },
  });
}

/**
 * Convenience helper for the sidebar badge: reviewers see a count of
 * pending requests they need to act on.
 *
 * Re-fetches every 60 s; React Query handles SWR by default so the
 * badge updates without manual invalidation.
 */
export function usePendingWCRCount(enabled: boolean = true) {
  return useQuery<number>({
    queryKey: keys.pendingCount(),
    enabled,
    refetchInterval: 60_000,
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<WorkflowChangeRequest[]>>(
        `${BASE}?status=pending`,
      );
      return data.data.length;
    },
  });
}
