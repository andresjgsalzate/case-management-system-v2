"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import type { ApiResponse, CaseTransfer } from "@/lib/types";

const TRANSFERS_KEY = "case-transfers";

export function useCaseTransfers(caseId: string) {
  return useQuery({
    queryKey: [TRANSFERS_KEY, caseId],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<CaseTransfer[]>>(
        `/cases/${caseId}/transfers`
      );
      return data.data ?? [];
    },
    enabled: !!caseId,
  });
}

export function useTransferCase(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { to_user_id: string; reason: string }) => {
      const { data } = await apiClient.post<ApiResponse<CaseTransfer>>(
        `/cases/${caseId}/transfer`,
        payload
      );
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [TRANSFERS_KEY, caseId] });
      qc.invalidateQueries({ queryKey: ["cases", caseId] });
      qc.invalidateQueries({ queryKey: ["cases"] });
    },
  });
}
