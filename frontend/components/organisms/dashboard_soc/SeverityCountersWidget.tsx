"use client";

interface Props {
  counters: Record<string, number>;
}

// Map lowercased priority names (backend returns them so) to display labels +
// color tokens. Tolerates Spanish (Critica/Alta/Media/Baja) + English forms.
const CELLS: Array<{ label: string; aliases: string[]; cls: string }> = [
  {
    label: "Crítica",
    aliases: ["critica", "critical"],
    cls: "border-red-500 bg-red-50 text-red-800",
  },
  {
    label: "Alta",
    aliases: ["alta", "high"],
    cls: "border-orange-400 bg-orange-50 text-orange-800",
  },
  {
    label: "Media",
    aliases: ["media", "medium"],
    cls: "border-yellow-400 bg-yellow-50 text-yellow-800",
  },
  {
    label: "Baja",
    aliases: ["baja", "low"],
    cls: "border-blue-400 bg-blue-50 text-blue-800",
  },
];

function _count(counters: Record<string, number>, aliases: string[]): number {
  return aliases.reduce((acc, key) => acc + (counters[key] ?? 0), 0);
}

export function SeverityCountersWidget({ counters }: Props) {
  return (
    <section className="rounded border bg-card p-3">
      <h3 className="mb-2 text-sm font-semibold">Casos abiertos por prioridad</h3>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {CELLS.map((cell) => (
          <div
            key={cell.label}
            className={`rounded border-l-4 px-3 py-2 ${cell.cls}`}
          >
            <p className="text-xs font-medium uppercase opacity-80">{cell.label}</p>
            <p className="font-mono text-2xl font-semibold">
              {_count(counters, cell.aliases)}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
