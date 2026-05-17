// Frontend hooks for Sub-spec 05 — Approval inbox + decide.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  ApprovalDecidePayload,
  ApprovalRequest,
  ApprovalStatus,
} from "@/lib/types";

const BASE = "/approval-requests";

const keys = {
  all: ["approval-requests"] as const,
  lists: () => [...keys.all, "list"] as const,
  list: (filters: ApprovalRequestsFilters) =>
    [...keys.lists(), filters] as const,
  detail: (id: string) => [...keys.all, "detail", id] as const,
};

export interface ApprovalRequestsFilters {
  status?: ApprovalStatus;
  case_id?: string;
  limit?: number;
}

// ── Reads ────────────────────────────────────────────────────────────────────

export function useApprovalInbox(filters: ApprovalRequestsFilters = {}) {
  return useQuery<ApprovalRequest[]>({
    queryKey: keys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      if (filters.case_id) params.set("case_id", filters.case_id);
      if (filters.limit) params.set("limit", String(filters.limit));
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<ApprovalRequest[]>>(
        `${BASE}${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
  });
}

export function useApprovalDetail(id: string | null | undefined) {
  return useQuery<ApprovalRequest>({
    queryKey: keys.detail(id ?? ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ApprovalRequest>>(
        `${BASE}/${id}`,
      );
      return data.data;
    },
  });
}

// ── Mutations ────────────────────────────────────────────────────────────────

export function useDecideApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id, payload,
    }: { id: string; payload: ApprovalDecidePayload }) => {
      const { data } = await apiClient.post<ApiResponse<unknown>>(
        `${BASE}/${id}/decide`,
        payload,
      );
      return data.data;
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: keys.all });
      qc.invalidateQueries({ queryKey: keys.detail(vars.id) });
    },
  });
}
