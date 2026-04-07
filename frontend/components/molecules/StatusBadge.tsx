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

interface StatusBadgeProps {
  status: string;
  label?: string;
  className?: string;
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const key = status.toLowerCase().replace(/\s+/g, "_");
  const config = STATUS_MAP[key] ?? { label: status, variant: "outline" as const };

  return (
    <Badge variant={config.variant} className={cn(className)}>
      {label ?? config.label}
    </Badge>
  );
}
