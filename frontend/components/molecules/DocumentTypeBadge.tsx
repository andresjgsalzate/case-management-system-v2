"use client";

import * as Icons from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { KBDocumentTypeRef } from "@/lib/types";

interface DocumentTypeBadgeProps {
  type: KBDocumentTypeRef | null | undefined;
  size?: "sm" | "md";
}

export function DocumentTypeBadge({ type, size = "sm" }: DocumentTypeBadgeProps) {
  if (!type) return null;
  const IconCmp = (Icons as unknown as Record<string, LucideIcon>)[type.icon] ??
    Icons.FileText;
  const dims = size === "sm" ? "text-xs px-1.5 py-0.5" : "text-sm px-2 py-1";
  const iconSize = size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md font-medium ${dims}`}
      style={{
        backgroundColor: `${type.color}1A`,
        color: type.color,
      }}
    >
      <IconCmp className={iconSize} />
      {type.name}
    </span>
  );
}
