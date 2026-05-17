// Frontend hooks for Sub-spec 05 — Playbook runs (n8n bridge).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  ManualTriggerWorkflowPayload,
  PlaybookRun,
  PlaybookRunCallback,
  PlaybookRunStatus,
} from "@/lib/types";

const BASE = "/playbook-runs";

const keys = {
  all: ["playbook-runs"] as const,
  lists: () => [...keys.all, "list"] as const,
  list: (filters: PlaybookRunsFilters) => [...keys.lists(), filters] as const,
  detail: (id: string) => [...keys.all, "detail", id] as const,
  callbacks: (id: string) => [...keys.all, "callbacks", id] as const,
};

export interface PlaybookRunsFilters {
  case_id?: string;
  status?: PlaybookRunStatus;
  limit?: number;
}

// ── Reads ────────────────────────────────────────────────────────────────────

export function usePlaybookRuns(filters: PlaybookRunsFilters = {}) {
  return useQuery<PlaybookRun[]>({
    queryKey: keys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.case_id) params.set("case_id", filters.case_id);
      if (filters.status) params.set("status", filters.status);
      if (filters.limit) params.set("limit", String(filters.limit));
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<PlaybookRun[]>>(
        `${BASE}${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
  });
}

export function usePlaybookRunDetail(id: string | null | undefined) {
  return useQuery<PlaybookRun>({
    queryKey: keys.detail(id ?? ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<PlaybookRun>>(
        `${BASE}/${id}`,
      );
      return data.data;
    },
  });
}

export function usePlaybookRunCallbacks(id: string | null | undefined) {
  return useQuery<PlaybookRunCallback[]>({
    queryKey: keys.callbacks(id ?? ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<PlaybookRunCallback[]>>(
        `${BASE}/${id}/callbacks`,
      );
      return data.data;
    },
  });
}

// ── Mutations ────────────────────────────────────────────────────────────────

export function useManualTriggerWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      caseId, payload,
    }: { caseId: string; payload: ManualTriggerWorkflowPayload }) => {
      const { data } = await apiClient.post<ApiResponse<PlaybookRun>>(
        `/cases/${caseId}/trigger-workflow`,
        payload,
      );
      return data.data;
    },
    onSuccess: (_run, vars) => {
      // Refresh the per-case list so the case detail tab updates immediately.
      qc.invalidateQueries({ queryKey: keys.lists() });
      qc.invalidateQueries({ queryKey: ["cases", vars.caseId] });
    },
  });
}
