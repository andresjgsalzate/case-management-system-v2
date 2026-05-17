// Frontend hook for Sub-spec 06 — Approval Inbox standalone page.
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  ApprovalInboxRow,
  ApprovalStatus,
} from "@/lib/types";

const BASE = "/operational/approval-requests/inbox";

export interface ApprovalInboxFilters {
  status?: ApprovalStatus | "all";
  case_id?: string;
  limit?: number;
  offset?: number;
}

export function useApprovalInbox(filters: ApprovalInboxFilters = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.case_id) params.set("case_id", filters.case_id);
  if (filters.limit !== undefined) params.set("limit", String(filters.limit));
  if (filters.offset !== undefined) params.set("offset", String(filters.offset));

  return useQuery<ApprovalInboxRow[]>({
    queryKey: ["approval-inbox", filters],
    queryFn: async () => {
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<ApprovalInboxRow[]>>(
        `${BASE}${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
    refetchInterval: 30_000,
  });
}
