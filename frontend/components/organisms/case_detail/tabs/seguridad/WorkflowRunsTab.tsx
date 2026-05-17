"use client";

import { PlaybookRunsTab } from "@/components/organisms/PlaybookRunsTab";

interface Props {
  caseId: string;
}

/** Thin wrapper around Sub-spec 05's PlaybookRunsTab — kept as a
 * separate component so the Seguridad sub-tabs router has a consistent
 * shape (one component per sub-tab). */
export function WorkflowRunsTab({ caseId }: Props) {
  return <PlaybookRunsTab caseId={caseId} />;
}
