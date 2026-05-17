"use client";

import type { ForensicHunt, ForensicHuntStatus } from "@/lib/types";

const STATUS_ICON: Record<ForensicHuntStatus, string> = {
  pending: "⏳",
  starting: "⏳",
  running: "⏳",
  completed: "✅",
  failed: "❌",
  timeout: "⏰",
  cancelled: "🚫",
};

interface Props {
  hunts: ForensicHunt[];
  onSelect: (hunt: ForensicHunt) => void;
}

export function HuntListTable({ hunts, onSelect }: Props) {
  if (hunts.length === 0) {
    return (
      <div className="text-sm text-gray-500 p-4 border rounded">
        No hay hunts forenses para este caso.
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {hunts.map((h) => (
        <li
          key={h.id}
          className="p-3 border rounded hover:bg-gray-50 cursor-pointer"
          onClick={() => onSelect(h)}
        >
          <div className="flex items-center gap-2 mb-1">
            <span aria-label={`status-${h.status}`}>
              {STATUS_ICON[h.status] ?? "?"}
            </span>
            <span className="font-mono text-sm font-medium">
              {h.chain_of_custody?.velo_hunt_id ?? h.id.slice(0, 8)}
            </span>
            <span className="text-sm text-gray-700">· {h.artifact_name}</span>
          </div>
          <div className="text-xs text-gray-600">
            {h.target_label ?? "—"} · {h.launched_via}
            {h.result_summary && (
              <> · {h.result_summary.total_rows} filas</>
            )}
          </div>
          {h.error && (
            <div className="text-xs text-red-600 mt-1 break-words">
              {h.error}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
