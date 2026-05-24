// Triage CRUD hooks. Backend exposes 3 endpoints under
// /api/v1/cases/{case_id}/triage. The "current" triage is the latest
// revision (highest version); history shows every revision.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  CaseTriage,
  CreateTriagePayload,
  TriageWithContext,
} from "@/lib/types";

const keys = {
  all: ["triage"] as const,
  current: (caseId: string) => [...keys.all, "current", caseId] as const,
  history: (caseId: string) => [...keys.all, "history", caseId] as const,
};

/** Latest triage revision + auto-derived context (parent taxonomy
 * name, sub name, resolved impact). Returns null when never triaged.
 */
export function useTriageCurrent(caseId: string | null) {
  return useQuery<TriageWithContext | null>({
    queryKey: keys.current(caseId ?? ""),
    enabled: !!caseId,
    staleTime: 60 * 1000,
    queryFn: async () => {
      const { data } = await apiClient.get<
        ApiResponse<TriageWithContext | null>
      >(`/cases/${caseId}/triage`);
      return data.data;
    },
  });
}

export function useTriageHistory(caseId: string | null) {
  return useQuery<CaseTriage[]>({
    queryKey: keys.history(caseId ?? ""),
    enabled: !!caseId,
    staleTime: 60 * 1000,
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<CaseTriage[]>>(
        `/cases/${caseId}/triage/history`,
      );
      return data.data;
    },
  });
}

export function useCreateTriage(caseId: string) {
  const qc = useQueryClient();
  return useMutation<CaseTriage, Error, CreateTriagePayload>({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post<ApiResponse<CaseTriage>>(
        `/cases/${caseId}/triage`,
        payload,
      );
      return data.data;
    },
    onSuccess: () => {
      // Refresh both the current triage AND the case (case.priority_id
      // may have been updated by the use case).
      qc.invalidateQueries({ queryKey: keys.current(caseId) });
      qc.invalidateQueries({ queryKey: keys.history(caseId) });
      qc.invalidateQueries({ queryKey: ["case", caseId] });
    },
  });
}
