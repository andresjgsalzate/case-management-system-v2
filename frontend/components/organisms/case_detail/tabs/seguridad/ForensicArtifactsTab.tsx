"use client";

/** Phase 1 stub — Sub-spec 07 (Velociraptor forensics) will replace this
 * with a `forensic_artifacts` table query + per-artifact download links.
 * For now, the n8n add_note / attach_artifact handlers prefix evidence
 * notes with "[n8n run X] Artifact attached..." so they appear in the
 * existing Notes tab. Operators can manually correlate until Sub-spec 07
 * lands.
 *
 * `caseId` accepted but unused — kept in the prop shape so the parent
 * router can call all sub-tabs uniformly. */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function ForensicArtifactsTab(_props: { caseId: string }) {
  return (
    <div className="rounded border border-dashed p-6 text-sm">
      <h3 className="mb-2 font-semibold">Forensic Artifacts (Phase 1)</h3>
      <p className="text-muted-foreground">
        Esta sección será implementada en Sub-spec 07 (Velociraptor
        forensics). Por ahora, los artefactos adjuntados por workflows n8n
        aparecen como notas con el prefijo{" "}
        <code className="rounded bg-muted px-1 font-mono">
          [n8n run XYZ] Artifact attached
        </code>{" "}
        en la pestaña de Notas.
      </p>
    </div>
  );
}
