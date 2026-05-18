// Frontend hook for Sub-spec 08 — template version history.
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  AlertReportTemplateVersion,
  ApiResponse,
} from "@/lib/types";

const keys = {
  all: ["alert-report-template-versions"] as const,
  list: (templateId: string) => [...keys.all, "list", templateId] as const,
};

export function useTemplateVersions(
  templateId: string | null | undefined,
) {
  return useQuery<AlertReportTemplateVersion[]>({
    queryKey: keys.list(templateId ?? ""),
    enabled: Boolean(templateId),
    queryFn: async () => {
      const { data } = await apiClient.get<
        ApiResponse<AlertReportTemplateVersion[]>
      >(`/alert-report-templates/${templateId}/versions`);
      return data.data;
    },
  });
}
