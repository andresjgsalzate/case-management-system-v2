"use client";

import { useState } from "react";

import { ApprovalCard } from "@/components/organisms/approvals/ApprovalCard";
import { ApprovalDecideModal } from "@/components/organisms/approvals/ApprovalDecideModal";
import { useApprovalInbox, type ApprovalInboxFilters } from "@/hooks/useApprovalInbox";
import type { ApprovalInboxRow } from "@/lib/types";

interface Props {
  initialFilters?: ApprovalInboxFilters;
}

export function ApprovalInboxList({ initialFilters }: Props) {
  const [filters, setFilters] = useState<ApprovalInboxFilters>(
    initialFilters ?? { status: "pending", limit: 50 },
  );
  const { data, isLoading, error, refetch } = useApprovalInbox(filters);

  const [targeted, setTargeted] = useState<{
    approval: ApprovalInboxRow;
    decision: "approved" | "rejected";
  } | null>(null);

  function start(decision: "approved" | "rejected", approval: ApprovalInboxRow) {
    setTargeted({ approval, decision });
  }

  return (
    <div className="space-y-3">
      <header className="flex flex-wrap items-center gap-2 rounded border bg-card p-2 text-xs">
        <label className="flex items-center gap-1">
          Estado:
          <select
            value={filters.status ?? "pending"}
            onChange={(e) =>
              setFilters((f) => ({ ...f, status: e.target.value as ApprovalInboxFilters["status"] }))
            }
            className="rounded border px-2 py-0.5"
          >
            <option value="pending">pending</option>
            <option value="approved">approved</option>
            <option value="rejected">rejected</option>
            <option value="timeout">timeout</option>
            <option value="cancelled">cancelled</option>
            <option value="all">todos</option>
          </select>
        </label>
      </header>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : error ? (
        <p className="text-sm text-red-600">Error al cargar approvals.</p>
      ) : !data || data.length === 0 ? (
        <p className="rounded border border-dashed p-6 text-sm text-muted-foreground">
          Sin approvals para este filtro.
        </p>
      ) : (
        <ul className="space-y-2">
          {data.map((a) => (
            <li key={a.id}>
              {a.status === "pending" ? (
                <ApprovalCard
                  approval={a}
                  onApprove={() => start("approved", a)}
                  onReject={() => start("rejected", a)}
                />
              ) : (
                <DecidedRow approval={a} />
              )}
            </li>
          ))}
        </ul>
      )}

      <ApprovalDecideModal
        isOpen={targeted !== null}
        approval={targeted?.approval ?? null}
        decision={targeted?.decision ?? "approved"}
        onClose={() => setTargeted(null)}
        onDecided={() => refetch()}
      />
    </div>
  );
}

function DecidedRow({ approval }: { approval: ApprovalInboxRow }) {
  const STATUS_COLOR: Record<string, string> = {
    approved: "bg-green-100 text-green-800",
    rejected: "bg-red-100 text-red-800",
    timeout: "bg-orange-100 text-orange-800",
    cancelled: "bg-gray-100 text-gray-700",
  };
  return (
    <article className="rounded border bg-muted/20 p-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium">{approval.requested_action}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {approval.action_category} · case {approval.case_id.slice(0, 8)}
          </p>
          {approval.decided_reason ? (
            <p className="mt-2 rounded bg-card px-2 py-1 text-xs">
              <span className="font-medium">Razón: </span>
              {approval.decided_reason}
            </p>
          ) : null}
        </div>
        <span
          className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium ${
            STATUS_COLOR[approval.status] ?? "bg-gray-100 text-gray-700"
          }`}
        >
          {approval.status}
        </span>
      </div>
    </article>
  );
}
