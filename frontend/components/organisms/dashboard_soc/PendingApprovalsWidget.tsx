"use client";

import Link from "next/link";

import type { ApprovalSummary } from "@/lib/types";

interface Props {
  count: number | null;
  approvals: ApprovalSummary[] | null;
}

/** Hidden entirely when the actor lacks `approvals:read` (backend returns null). */
export function PendingApprovalsWidget({ count, approvals }: Props) {
  if (count === null || approvals === null) return null;

  return (
    <section className="rounded border bg-card p-3">
      <header className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          Approvals pendientes{" "}
          <span className="text-muted-foreground">({count})</span>
        </h3>
        <Link
          href="/approvals"
          className="text-xs text-blue-600 hover:underline"
        >
          Ver todos
        </Link>
      </header>

      {approvals.length === 0 ? (
        <p className="rounded border border-dashed p-3 text-xs text-muted-foreground">
          Sin approvals pendientes.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {approvals.map((a) => (
            <li
              key={a.id}
              className="flex items-center justify-between gap-3 rounded border px-2 py-1.5 text-xs"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{a.requested_action}</p>
                <p className="text-muted-foreground">
                  {a.action_category} · case {a.case_id.slice(0, 8)}
                </p>
              </div>
              <span className="text-[10px] text-muted-foreground">
                Expira {new Date(a.timeout_at).toLocaleTimeString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
