"use client";

import { ApprovalInboxList } from "@/components/organisms/approvals/ApprovalInboxList";

export default function ApprovalsInboxPage() {
  return (
    <div className="space-y-4 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold">Approval Inbox</h1>
        <p className="text-sm text-muted-foreground">
          Aprobar o rechazar acciones solicitadas por workflows n8n. La cuenta
          regresiva indica cuándo expira la solicitud (auto-timeout).
        </p>
      </header>
      <ApprovalInboxList />
    </div>
  );
}
