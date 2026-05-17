"use client";

import type { ForensicArtifactParameter } from "@/lib/types";

interface Props {
  parameters: ForensicArtifactParameter[];
  values: Record<string, unknown>;
  onChange: (values: Record<string, unknown>) => void;
}

export function ArtifactParametersForm({
  parameters,
  values,
  onChange,
}: Props) {
  if (parameters.length === 0) {
    return (
      <div className="text-sm text-gray-500">
        Este artifact no requiere parámetros.
      </div>
    );
  }

  function update(key: string, value: unknown) {
    onChange({ ...values, [key]: value });
  }

  return (
    <div className="space-y-3">
      {parameters.map((p) => {
        const current = values[p.name];
        const displayValue =
          typeof current === "string"
            ? current
            : current === undefined && typeof p.default === "string"
              ? p.default
              : current === undefined
                ? ""
                : String(current);

        return (
          <div key={p.name}>
            <label
              className="block text-sm font-medium mb-1"
              htmlFor={`param-${p.name}`}
            >
              {p.name}
            </label>
            {p.description && (
              <p className="text-xs text-gray-600 mb-1">{p.description}</p>
            )}
            <input
              id={`param-${p.name}`}
              type="text"
              value={displayValue}
              onChange={(e) => update(p.name, e.target.value)}
              className="w-full border rounded px-2 py-1 text-sm"
            />
          </div>
        );
      })}
    </div>
  );
}
