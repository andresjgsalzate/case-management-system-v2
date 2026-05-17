"use client";

import { useState } from "react";

import { useForensicHunts } from "@/hooks/useForensicHunts";
import { useHasPermission } from "@/hooks/useHasPermission";
import type { ForensicHunt } from "@/lib/types";

import { HuntDetailDrawer } from "./HuntDetailDrawer";
import { HuntLauncherModal } from "./HuntLauncherModal";
import { HuntListTable } from "./HuntListTable";

interface Props {
  caseId: string;
}

export function ForensicArtifactsTab({ caseId }: Props) {
  const huntsQuery = useForensicHunts({ case_id: caseId });
  const hunts = huntsQuery.data ?? [];

  const [launcherOpen, setLauncherOpen] = useState(false);
  const [selectedHunt, setSelectedHunt] = useState<ForensicHunt | null>(null);

  const canLaunchRO = useHasPermission("forensic", "launch_ro");

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">
          Hunts forenses ({hunts.length})
        </h2>
        {canLaunchRO && (
          <button
            type="button"
            onClick={() => setLauncherOpen(true)}
            className="px-3 py-1 bg-blue-600 text-white rounded text-sm"
          >
            + Lanzar hunt
          </button>
        )}
      </div>

      {huntsQuery.isLoading && (
        <div className="text-sm text-gray-500">Cargando hunts...</div>
      )}

      {!huntsQuery.isLoading && (
        <HuntListTable hunts={hunts} onSelect={setSelectedHunt} />
      )}

      <HuntLauncherModal
        caseId={caseId}
        isOpen={launcherOpen}
        onClose={() => setLauncherOpen(false)}
        onLaunched={() => {
          // useLaunchHunt already invalidates ["forensic-hunts"] on success
          // (Task 16) so the list refetches automatically. Hook left as a
          // future-proof callback for callers that want side effects.
        }}
      />

      <HuntDetailDrawer
        huntId={selectedHunt?.id ?? null}
        onClose={() => setSelectedHunt(null)}
      />
    </div>
  );
}
