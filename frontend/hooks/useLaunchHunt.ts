// Frontend hook for Sub-spec 07 — POST to launch a hunt from the UI.
//
// Invalidates the hunts list on success so the Hunt Launcher modal can
// close and the parent list re-renders the new pending/running row.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse, ForensicHunt, LaunchHuntRequest,
} from "@/lib/types";

interface LaunchHuntInput {
  caseId: string;
  body: LaunchHuntRequest;
}

export function useLaunchHunt() {
  const queryClient = useQueryClient();

  return useMutation<ForensicHunt, Error, LaunchHuntInput>({
    mutationFn: async ({ caseId, body }) => {
      const { data } = await apiClient.post<ApiResponse<ForensicHunt>>(
        `/forensic/cases/${caseId}/hunts`,
        body,
      );
      return data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["forensic-hunts"] });
    },
  });
}

interface CancelHuntInput {
  huntId: string;
  reason?: string;
}

export function useCancelHunt() {
  const queryClient = useQueryClient();

  return useMutation<ForensicHunt, Error, CancelHuntInput>({
    mutationFn: async ({ huntId, reason }) => {
      const { data } = await apiClient.post<ApiResponse<ForensicHunt>>(
        `/forensic/hunts/${huntId}/cancel`,
        { reason: reason ?? null },
      );
      return data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["forensic-hunts"] });
    },
  });
}
