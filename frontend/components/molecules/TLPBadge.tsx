import { cn } from "@/lib/utils";
import type { TLP } from "@/lib/types";

const TLP_MAP: Record<TLP, { label: string; className: string }> = {
  white: { label: "TLP: WHITE", className: "border-gray-300 bg-gray-50 text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200" },
  green: { label: "TLP: GREEN", className: "border-green-400 bg-green-50 text-green-800 dark:border-green-700 dark:bg-green-950 dark:text-green-300" },
  amber: { label: "TLP: AMBER", className: "border-yellow-400 bg-yellow-50 text-yellow-800 dark:border-yellow-700 dark:bg-yellow-950 dark:text-yellow-300" },
  red:   { label: "TLP: RED",   className: "border-red-400 bg-red-50 text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-300" },
};

interface TLPBadgeProps {
  tlp: TLP;
  className?: string;
}

export function TLPBadge({ tlp, className }: TLPBadgeProps) {
  const config = TLP_MAP[tlp] ?? TLP_MAP.white;
  return (
    <span
      className={cn(
        "inline-block rounded border px-2 py-0.5 text-xs font-semibold tracking-wider",
        config.className,
        className,
      )}
    >
      {config.label}
    </span>
  );
}
