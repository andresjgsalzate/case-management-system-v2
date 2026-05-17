"use client";

import { ApprovalInboxList } from "@/components/organisms/approvals/ApprovalInboxList";

interface Props {
  caseId: string;
}

/** Per-case approvals view — reuses the inbox list filtered by case_id. */
export function ApprovalsTab({ caseId }: Props) {
  return (
    <ApprovalInboxList
      initialFilters={{ case_id: caseId, status: "all", limit: 100 }}
    />
  );
}
