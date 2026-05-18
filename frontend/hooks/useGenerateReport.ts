// Frontend hook for Sub-spec 08 — generate + download alert report PDF.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  CaseGeneratedReport,
  GenerateAlertReportRequest,
} from "@/lib/types";

interface GenerateInput {
  caseId: string;
  body: GenerateAlertReportRequest;
}

export function useGenerateAlertReport() {
  const queryClient = useQueryClient();
  return useMutation<CaseGeneratedReport, Error, GenerateInput>({
    mutationFn: async ({ caseId, body }) => {
      const { data } = await apiClient.post<
        ApiResponse<CaseGeneratedReport>
      >(`/cases/${caseId}/alert-reports`, body);
      return data.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["alert-reports", "case", variables.caseId],
      });
    },
  });
}

/**
 * Trigger a PDF download for a generated report. Browsers handle the actual
 * save dialog; we hit the streaming endpoint and let the browser persist.
 *
 * Returns the URL the caller should navigate to (or pass to an anchor's
 * ``href``). Authentication header injection comes from the apiClient axios
 * instance, but this is a streaming response — easiest UX is a regular
 * <a download href="..."> that the browser fetches with its credentials
 * cookie / token, or a JS-driven blob download.
 */
export function buildDownloadUrl(reportId: string): string {
  // The apiClient prefixes /api/proxy on the browser side. Mirroring that
  // so anchor hrefs route through the same path.
  return `/api/proxy/alert-reports/${reportId}/download`;
}

/**
 * Fetch the PDF as a Blob (for in-app preview or programmatic save).
 *
 * Returns the bytes + suggested filename extracted from the
 * Content-Disposition response header (falls back to ``report.pdf``).
 */
export async function downloadAlertReportBlob(
  reportId: string,
): Promise<{ blob: Blob; filename: string }> {
  const response = await apiClient.get(
    `/alert-reports/${reportId}/download`,
    { responseType: "blob" },
  );
  const cd: string = (response.headers["content-disposition"] as string) ?? "";
  const match = cd.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : "report.pdf";
  return { blob: response.data as Blob, filename };
}
