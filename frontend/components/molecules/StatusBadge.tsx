import React from "react";
import { Badge, type BadgeVariant } from "@/components/atoms/Badge";
import { cn } from "@/lib/utils";

export type { BadgeVariant };

const STATUS_MAP: Record<string, { label: string; variant: "default" | "success" | "warning" | "destructive" | "outline" | "secondary" }> = {
  // Common slugs
  open:        { label: "Abierto",      variant: "default" },
  in_progress: { label: "En progreso",  variant: "warning" },
  pending:     { label: "Pendiente",    variant: "warning" },
  resolved:    { label: "Resuelto",     variant: "success" },
  closed:      { label: "Cerrado",      variant: "outline" },
  cancelled:   { label: "Cancelado",    variant: "destructive" },
  // KB article statuses
  draft:       { label: "Borrador",     variant: "secondary" },
  in_review:   { label: "En revisión",  variant: "warning" },
  approved:    { label: "Aprobado",     variant: "success" },
  published:   { label: "Publicado",    variant: "default" },
  rejected:    { label: "Rechazado",    variant: "destructive" },
};

const BREATHE_COLORS: Record<BadgeVariant, string> = {
  default:     "rgba(59, 130, 246, 0.45)",
  success:     "rgba(16, 185, 129, 0.45)",
  warning:     "rgba(245, 158, 11, 0.45)",
  destructive: "rgba(239, 68, 68, 0.45)",
  outline:     "rgba(148, 163, 184, 0.35)",
  secondary:   "rgba(148, 163, 184, 0.35)",
};

interface StatusBadgeProps {
  status: string;
  label?: string;
  className?: string;
  pulse?: boolean;
}

export function StatusBadge({ status, label, className, pulse }: StatusBadgeProps) {
  const key = status.toLowerCase().replace(/\s+/g, "_");
  const config = STATUS_MAP[key] ?? { label: status, variant: "outline" as const };

  return (
    <Badge
      variant={config.variant}
      className={cn(pulse && "animate-breathe", className)}
      style={pulse ? { "--breathe-color": BREATHE_COLORS[config.variant] } as React.CSSProperties : undefined}
    >
      {label ?? config.label}
    </Badge>
  );
}
