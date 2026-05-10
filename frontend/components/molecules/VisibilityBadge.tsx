"use client";

import { Globe, Users, Lock } from "lucide-react";
import type { KBVisibility } from "@/lib/types";

interface Props {
  visibility: KBVisibility;
  size?: "xs" | "sm";
}

const META: Record<KBVisibility, { label: string; icon: typeof Globe; bg: string; text: string }> = {
  private: { label: "Privado", icon: Lock,   bg: "bg-slate-100 dark:bg-slate-800",   text: "text-slate-700 dark:text-slate-300" },
  team:    { label: "Equipo",  icon: Users,  bg: "bg-blue-50 dark:bg-blue-950/40",   text: "text-blue-700 dark:text-blue-300" },
  public:  { label: "Público", icon: Globe,  bg: "bg-emerald-50 dark:bg-emerald-950/40", text: "text-emerald-700 dark:text-emerald-300" },
};

export function VisibilityBadge({ visibility, size = "xs" }: Props) {
  const m = META[visibility];
  const Icon = m.icon;
  const sz = size === "xs" ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-0.5";
  const iconSz = size === "xs" ? "h-3 w-3" : "h-3.5 w-3.5";
  return (
    <span className={`inline-flex items-center gap-1 rounded-md ${m.bg} ${m.text} ${sz}`}>
      <Icon className={iconSz} />
      {m.label}
    </span>
  );
}
