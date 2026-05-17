"use client";

import type { ForensicHunt } from "@/lib/types";

interface Props {
  hunt: ForensicHunt;
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="inline font-medium">{label}:</dt>
      <dd
        className={`inline ml-2 ${
          mono ? "font-mono text-xs break-all" : ""
        }`}
      >
        {value ?? "—"}
      </dd>
    </div>
  );
}

export function ChainOfCustodyPanel({ hunt }: Props) {
  const coc = hunt.chain_of_custody;
  if (!coc) return null;

  return (
    <section
      aria-labelledby="coc-title"
      className="border rounded p-3 bg-gray-50"
    >
      <h3 id="coc-title" className="font-semibold mb-2">
        🔒 Cadena de custodia
      </h3>
      <dl className="text-sm space-y-1">
        <Field label="Hash del resultado" value={coc.result_hash} mono />
        <Field label="Velo Hunt ID" value={coc.velo_hunt_id} mono />
        <Field label="Velo Org ID" value={coc.velo_org_id} mono />
        <Field
          label="Lanzado"
          value={new Date(hunt.started_at).toLocaleString()}
        />
        {hunt.completed_at && (
          <Field
            label="Completado"
            value={new Date(hunt.completed_at).toLocaleString()}
          />
        )}
        {coc.approval_request_id && (
          <Field
            label="Approval"
            value={coc.approval_request_id}
            mono
          />
        )}
      </dl>
    </section>
  );
}
