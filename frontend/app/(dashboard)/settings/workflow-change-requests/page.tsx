"use client";

import { useState } from "react";
import { Plus, ArrowLeft } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/atoms/Button";
import { useHasPermission } from "@/hooks/useHasPermission";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import { WorkflowChangeRequestFormModal } from "@/components/organisms/WorkflowChangeRequestFormModal";
import { WorkflowChangeRequestList } from "@/components/organisms/WorkflowChangeRequestList";
import { WorkflowChangeRequestReviewModal } from "@/components/organisms/WorkflowChangeRequestReviewModal";
import type { WorkflowChangeRequest } from "@/lib/types";

export default function WorkflowChangeRequestsPage() {
  usePermissionGuard("workflow_change_requests", "read");
  const canCreate = useHasPermission("workflow_change_requests", "create");

  const [createOpen, setCreateOpen] = useState(false);
  const [reviewing, setReviewing] = useState<WorkflowChangeRequest | null>(
    null
  );

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link
          href="/settings"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-2"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Configuración
        </Link>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-foreground">
              Solicitudes de cambio en workflows
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5 max-w-2xl">
              Control compensatorio mientras CMS opera en n8n Community.
              Admins sin acceso directo al editor proponen modificaciones
              auditablemente; el revisor único las aprueba e implementa.
            </p>
          </div>
          {canCreate && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Nueva solicitud
            </Button>
          )}
        </div>
      </div>

      <WorkflowChangeRequestList
        onOpenReview={(wcr) => setReviewing(wcr)}
      />

      <WorkflowChangeRequestFormModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
      />

      <WorkflowChangeRequestReviewModal
        wcr={reviewing}
        onClose={() => setReviewing(null)}
      />
    </div>
  );
}
