"use client";

import { Globe, Users, Lock, Clock } from "lucide-react";
import type { KBVisibility } from "@/lib/types";

interface Props {
  value: KBVisibility;
  onChange: (v: KBVisibility) => void;
  /** Si hay cambio pendiente de aprobación, lo mostramos como info */
  pending?: KBVisibility | null;
  disabled?: boolean;
}

const OPTIONS: { value: KBVisibility; label: string; description: string; icon: typeof Globe; color: string }[] = [
  {
    value: "private",
    label: "Privado",
    description: "Solo tú puedes verlo",
    icon: Lock,
    color: "text-slate-600",
  },
  {
    value: "team",
    label: "Equipo",
    description: "Tu equipo puede verlo",
    icon: Users,
    color: "text-blue-600",
  },
  {
    value: "public",
    label: "Público",
    description: "Todos pueden verlo (requiere aprobación)",
    icon: Globe,
    color: "text-emerald-600",
  },
];

export function VisibilitySelect({ value, onChange, pending, disabled }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {OPTIONS.map((opt) => {
          const Icon = opt.icon;
          const selected = value === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              disabled={disabled}
              onClick={() => onChange(opt.value)}
              className={`flex flex-col items-start gap-1 rounded-md border-2 p-3 text-left transition-colors disabled:opacity-50 ${
                selected
                  ? "border-primary bg-primary/5"
                  : "border-border bg-card hover:border-primary/40 hover:bg-muted/40"
              }`}
            >
              <div className="flex items-center gap-1.5">
                <Icon className={`h-4 w-4 ${opt.color}`} />
                <span className="text-sm font-medium text-foreground">{opt.label}</span>
              </div>
              <p className="text-xs text-muted-foreground">{opt.description}</p>
            </button>
          );
        })}
      </div>

      {pending && pending !== value && (
        <div className="flex items-center gap-2 rounded-md bg-amber-50 dark:bg-amber-950/20 border border-amber-300 dark:border-amber-900 px-3 py-2 text-xs text-amber-900 dark:text-amber-200">
          <Clock className="h-3.5 w-3.5 shrink-0" />
          <span>
            Cambio pendiente de aprobación: <strong>{labelOf(pending)}</strong>
          </span>
        </div>
      )}
    </div>
  );
}

function labelOf(v: KBVisibility): string {
  return OPTIONS.find((o) => o.value === v)?.label ?? v;
}
