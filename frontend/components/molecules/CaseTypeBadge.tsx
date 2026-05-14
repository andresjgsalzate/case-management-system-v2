"use client";

import { Badge, type BadgeVariant } from "@/components/atoms/Badge";
import type { CaseType } from "@/lib/types";

const CASE_TYPE_MAP: Record<
  CaseType,
  { label: string; variant: BadgeVariant }
> = {
  request: {
    label: "Solicitud",
    variant: "default",
  },
  incident: {
    label: "Incidencia",
    variant: "destructive",
  },
  event: {
    label: "Evento",
    variant: "warning",
  },
};

interface CaseTypeBadgeProps {
  caseType: CaseType;
  className?: string;
}

export function CaseTypeBadge({ caseType, className }: CaseTypeBadgeProps) {
  const config = CASE_TYPE_MAP[caseType];

  return (
    <Badge variant={config.variant} className={className}>
      {config.label}
    </Badge>
  );
}
