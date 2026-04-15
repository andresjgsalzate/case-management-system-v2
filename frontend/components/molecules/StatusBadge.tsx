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

const BREATHE_CLASS: Record<BadgeVariant, string> = {
  default:     "breathe-blue",
  success:     "breathe-emerald",
  warning:     "breathe-amber",
  destructive: "breathe-red",
  outline:     "breathe-slate",
  secondary:   "breathe-slate",
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
      className={cn(pulse && BREATHE_CLASS[config.variant], className)}
    >
      {label ?? config.label}
    </Badge>
  );
}
