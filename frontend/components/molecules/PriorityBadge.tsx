import { AlertTriangle, ArrowUp, ArrowDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

const PRIORITY_MAP: Record<string, { label: string; icon: React.ElementType; className: string }> = {
  critical:  { label: "Crítica",  icon: AlertTriangle, className: "text-red-600 dark:text-red-400" },
  urgent:    { label: "Urgente",  icon: AlertTriangle, className: "text-orange-600 dark:text-orange-400" },
  high:      { label: "Alta",     icon: ArrowUp,       className: "text-amber-600 dark:text-amber-400" },
  medium:    { label: "Media",    icon: Minus,         className: "text-blue-600 dark:text-blue-400" },
  low:       { label: "Baja",     icon: ArrowDown,     className: "text-muted-foreground" },
  alta:      { label: "Alta",     icon: ArrowUp,       className: "text-amber-600 dark:text-amber-400" },
  media:     { label: "Media",    icon: Minus,         className: "text-blue-600 dark:text-blue-400" },
  baja:      { label: "Baja",     icon: ArrowDown,     className: "text-muted-foreground" },
};

interface PriorityBadgeProps {
  priority: string;
  showLabel?: boolean;
  className?: string;
}

export function PriorityBadge({ priority, showLabel = true, className }: PriorityBadgeProps) {
  const key = priority.toLowerCase();
  const config = PRIORITY_MAP[key] ?? {
    label: priority,
    icon: Minus,
    className: "text-muted-foreground",
  };
  const Icon = config.icon;

  return (
    <span className={cn("inline-flex items-center gap-1 text-xs font-medium", config.className, className)}>
      <Icon className="h-3.5 w-3.5 shrink-0" />
      {showLabel && config.label}
    </span>
  );
}
