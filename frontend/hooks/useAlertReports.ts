// Frontend hooks for Sub-spec 08 — generated reports per case.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  AlertReportIntegrityCheck,
  ApiResponse,
  CaseGeneratedReport,
} from "@/lib/types";

const keys = {
  all: ["alert-reports"] as const,
  forCase: (caseId: string) => [...keys.all, "case", caseId] as const,
  detail: (reportId: string) => [...keys.all, "detail", reportId] as const,
  verify: (reportId: string) => [...keys.all, "verify", reportId] as const,
};

export function useAlertReportsForCase(caseId: string | null | undefined) {
  return useQuery<CaseGeneratedReport[]>({
    queryKey: keys.forCase(caseId ?? ""),
    enabled: Boolean(caseId),
    queryFn: async () => {
      const { data } = await apiClient.get<
        ApiResponse<CaseGeneratedReport[]>
      >(`/cases/${caseId}/alert-reports`);
      return data.data;
    },
  });
}

export function useAlertReportDetail(reportId: string | null | undefined) {
  return useQuery<CaseGeneratedReport>({
    queryKey: keys.detail(reportId ?? ""),
    enabled: Boolean(reportId),
    queryFn: async () => {
      const { data } = await apiClient.get<
        ApiResponse<CaseGeneratedReport>
      >(`/alert-reports/${reportId}`);
      return data.data;
    },
  });
}

export function useVerifyAlertReport(
  reportId: string | null | undefined,
) {
  return useQuery<AlertReportIntegrityCheck>({
    queryKey: keys.verify(reportId ?? ""),
    enabled: false,  // manual trigger via .refetch()
    queryFn: async () => {
      const { data } = await apiClient.get<
        ApiResponse<AlertReportIntegrityCheck>
      >(`/alert-reports/${reportId}/verify`);
      return data.data;
    },
  });
}

interface DeleteInput {
  reportId: string;
  caseId: string;
  reason: string;
}

export function useDeleteAlertReport() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, DeleteInput>({
    mutationFn: async ({ reportId, reason }) => {
      // axios.delete needs a body via `data:` config.
      await apiClient.delete(`/alert-reports/${reportId}`, {
        data: { reason },
      });
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: keys.forCase(variables.caseId),
      });
      queryClient.invalidateQueries({
        queryKey: keys.detail(variables.reportId),
      });
    },
  });
}
