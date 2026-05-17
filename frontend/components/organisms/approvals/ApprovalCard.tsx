"use client";

import { Check, Clock, X } from "lucide-react";
import { useEffect, useState } from "react";

import type { ApprovalInboxRow } from "@/lib/types";

interface Props {
  approval: ApprovalInboxRow;
  onApprove: () => void;
  onReject: () => void;
  disabled?: boolean;
}

const CATEGORY_COLOR: Record<string, string> = {
  host_quarantine:  "bg-red-100 text-red-800",
  account_block:    "bg-orange-100 text-orange-800",
  firewall_rule_add: "bg-purple-100 text-purple-800",
  email_purge:      "bg-indigo-100 text-indigo-800",
  process_kill:     "bg-pink-100 text-pink-800",
  data_wipe:        "bg-rose-100 text-rose-800",
  custom:           "bg-gray-100 text-gray-700",
};

function _countdown(timeoutAt: string): string {
  const ms = new Date(timeoutAt).getTime() - Date.now();
  if (ms <= 0) return "Vencido";
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.floor((ms % 60_000) / 1000);
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
  }
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

export function ApprovalCard({
  approval, onApprove, onReject, disabled,
}: Props) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);
  void tick;  // re-render trigger only

  const remaining = _countdown(approval.timeout_at);
  const isUrgent = remaining !== "Vencido"
    && new Date(approval.timeout_at).getTime() - Date.now() < 5 * 60_000;
  const isExpired = remaining === "Vencido";

  const categoryCls = CATEGORY_COLOR[approval.action_category]
    ?? CATEGORY_COLOR.custom;

  return (
    <article className="rounded border bg-card p-3">
      <header className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium">{approval.requested_action}</p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className={`rounded px-1.5 py-0.5 ${categoryCls}`}>
              {approval.action_category}
            </span>
            <span className="font-mono">case {approval.case_id.slice(0, 8)}</span>
            <span>· workflow: <span className="font-mono">{approval.requested_by_workflow.slice(0, 32)}</span></span>
          </p>
        </div>
        <div
          className={`flex shrink-0 items-center gap-1 rounded px-2 py-1 text-xs font-medium ${
            isExpired
              ? "bg-red-100 text-red-800"
              : isUrgent
              ? "bg-amber-100 text-amber-800"
              : "bg-gray-100 text-gray-700"
          }`}
        >
          <Clock className="h-3 w-3" />
          {remaining}
        </div>
      </header>

      {Object.keys(approval.context_payload || {}).length > 0 ? (
        <details className="mb-2 rounded border bg-muted/20 text-xs">
          <summary className="cursor-pointer px-2 py-1 hover:bg-muted/40">
            Evidencia ({Object.keys(approval.context_payload).length} campos)
          </summary>
          <pre className="overflow-auto p-2 text-[11px]">
            {JSON.stringify(approval.context_payload, null, 2)}
          </pre>
        </details>
      ) : null}

      <footer className="flex justify-end gap-2 border-t pt-2">
        <button
          type="button"
          onClick={onReject}
          disabled={disabled || isExpired}
          className="inline-flex items-center gap-1 rounded border border-red-300 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
        >
          <X className="h-3 w-3" /> Rechazar
        </button>
        <button
          type="button"
          onClick={onApprove}
          disabled={disabled || isExpired}
          className="inline-flex items-center gap-1 rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
        >
          <Check className="h-3 w-3" /> Aprobar
        </button>
      </footer>
    </article>
  );
}
