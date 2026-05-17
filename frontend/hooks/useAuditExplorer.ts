// Frontend hooks for Sub-spec 06 — Audit Explorer query + CSV export.
import { useMutation, useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  AuditExplorerFilters,
  AuditQueryResultDTO,
} from "@/lib/types";

const BASE = "/operational/audit-explorer";

/** Returns the audit query result for the given filters. Pass `enabled=false`
 * (default when filters is null) to wait for the user to hit "Buscar". */
export function useAuditExplorer(
  filters: AuditExplorerFilters | null,
) {
  return useQuery<AuditQueryResultDTO>({
    queryKey: ["audit-explorer", filters],
    enabled: filters !== null,
    queryFn: async () => {
      const { data } = await apiClient.post<ApiResponse<AuditQueryResultDTO>>(
        `${BASE}/query`,
        filters,
      );
      return data.data;
    },
  });
}

/** Mutation that triggers a CSV download via the browser. The endpoint
 * returns `Content-Disposition: attachment` so the browser handles the save
 * dialog automatically. */
export function useAuditExplorerCsvExport() {
  return useMutation({
    mutationFn: async (filters: AuditExplorerFilters) => {
      const response = await apiClient.post(`${BASE}/export`, filters, {
        responseType: "blob",
      });
      const blob = new Blob([response.data as BlobPart], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "audit-export.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      return { ok: true };
    },
  });
}
