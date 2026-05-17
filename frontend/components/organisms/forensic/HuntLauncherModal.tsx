"use client";

import { useState } from "react";

import { useLaunchHunt } from "@/hooks/useLaunchHunt";
import type { ForensicArtifact } from "@/lib/types";

import { ArtifactParametersForm } from "./ArtifactParametersForm";
import { ArtifactPicker } from "./ArtifactPicker";
import { TargetClientsPicker } from "./TargetClientsPicker";

interface Props {
  caseId: string;
  isOpen: boolean;
  onClose: () => void;
  onLaunched: () => void;
}

export function HuntLauncherModal({
  caseId,
  isOpen,
  onClose,
  onLaunched,
}: Props) {
  const [artifact, setArtifact] = useState<ForensicArtifact | null>(null);
  const [parameters, setParameters] = useState<Record<string, unknown>>({});
  const [targets, setTargets] = useState<string[]>([]);
  const [timeoutSeconds, setTimeoutSeconds] = useState<number | undefined>(
    undefined,
  );

  const launchMutation = useLaunchHunt();

  if (!isOpen) return null;

  function selectArtifact(a: ForensicArtifact) {
    setArtifact(a);
    setParameters({});
    setTargets([]);
    setTimeoutSeconds(undefined);
  }

  async function handleLaunch() {
    if (!artifact || targets.length === 0) return;
    await launchMutation.mutateAsync({
      caseId,
      body: {
        artifact_id: artifact.id,
        parameters,
        target_clients: targets,
        timeout_seconds: timeoutSeconds,
      },
    });
    onLaunched();
    onClose();
  }

  const timeoutMinutes =
    timeoutSeconds !== undefined
      ? Math.round(timeoutSeconds / 60)
      : artifact
        ? Math.round(artifact.default_timeout_seconds / 60)
        : 30;

  const errorMessage = launchMutation.error?.message ?? null;
  const isLaunching = launchMutation.isPending;
  const canLaunch =
    Boolean(artifact) && targets.length > 0 && !isLaunching;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="hunt-launcher-title"
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    >
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 id="hunt-launcher-title" className="text-xl font-semibold">
            Lanzar hunt forense
          </h2>
          <button
            type="button"
            aria-label="Cerrar"
            onClick={onClose}
            className="text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <section className="mb-6">
          <h3 className="font-medium mb-2">1. Seleccionar artifact</h3>
          <ArtifactPicker
            selectedArtifactId={artifact?.id ?? null}
            onSelect={selectArtifact}
          />
        </section>

        {artifact && (
          <>
            <section className="mb-6">
              <h3 className="font-medium mb-2">2. Seleccionar target</h3>
              <TargetClientsPicker
                selected={targets}
                onChange={setTargets}
              />
            </section>

            <section className="mb-6">
              <h3 className="font-medium mb-2">3. Parámetros</h3>
              <ArtifactParametersForm
                parameters={artifact.parameters_schema ?? []}
                values={parameters}
                onChange={setParameters}
              />
            </section>

            <section className="mb-6">
              <label
                className="block font-medium mb-2"
                htmlFor="hunt-timeout-min"
              >
                Timeout (minutos)
              </label>
              <input
                id="hunt-timeout-min"
                type="number"
                min={1}
                value={timeoutMinutes}
                onChange={(e) => {
                  const mins = Number(e.target.value);
                  setTimeoutSeconds(
                    Number.isFinite(mins) && mins > 0 ? mins * 60 : undefined,
                  );
                }}
                className="border rounded px-2 py-1 w-32"
              />
            </section>
          </>
        )}

        {errorMessage && (
          <div className="text-red-600 text-sm mb-3" role="alert">
            {errorMessage}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border rounded"
            disabled={isLaunching}
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleLaunch}
            disabled={!canLaunch}
            className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
          >
            {isLaunching ? "Lanzando..." : "Lanzar hunt"}
          </button>
        </div>
      </div>
    </div>
  );
}
