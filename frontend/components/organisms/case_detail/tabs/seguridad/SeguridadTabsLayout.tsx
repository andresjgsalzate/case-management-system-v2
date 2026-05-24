"use client";

import { useState } from "react";

import { AlertReportTab } from "./AlertReportTab";
import { ApprovalsTab } from "./ApprovalsTab";
import { ForensicArtifactsTab } from "./ForensicArtifactsTab";
import { TriageTab } from "./TriageTab";
import { WazuhEventsTab } from "./WazuhEventsTab";
import { WorkflowRunsTab } from "./WorkflowRunsTab";

type SubTab =
  | "triage"
  | "wazuh"
  | "forensic"
  | "approvals"
  | "workflows"
  | "report";

const SUB_TABS: { key: SubTab; label: string }[] = [
  // Triage first: the operational starting point for every SOC case.
  { key: "triage", label: "Triage" },
  { key: "wazuh", label: "Wazuh Events" },
  { key: "forensic", label: "Forensic Artifacts" },
  { key: "approvals", label: "Approvals" },
  { key: "workflows", label: "Workflow Runs" },
  { key: "report", label: "Alert Report" },
];

interface Props {
  caseId: string;
}

export function SeguridadTabsLayout({ caseId }: Props) {
  const [active, setActive] = useState<SubTab>("triage");

  return (
    <div className="space-y-3">
      <nav className="flex flex-wrap gap-1 border-b">
        {SUB_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setActive(t.key)}
            className={`border-b-2 px-3 py-1.5 text-xs transition-colors ${
              active === t.key
                ? "border-blue-600 font-medium text-blue-700"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div>
        {active === "triage" && <TriageTab caseId={caseId} />}
        {active === "wazuh" && <WazuhEventsTab caseId={caseId} />}
        {active === "forensic" && <ForensicArtifactsTab caseId={caseId} />}
        {active === "approvals" && <ApprovalsTab caseId={caseId} />}
        {active === "workflows" && <WorkflowRunsTab caseId={caseId} />}
        {active === "report" && <AlertReportTab caseId={caseId} />}
      </div>
    </div>
  );
}
