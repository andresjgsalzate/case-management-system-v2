"use client";

import * as Icons from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useDocumentTypes } from "@/hooks/useKB";

interface DocumentTypeSelectProps {
  value: string | null;
  onChange: (id: string | null) => void;
}

export function DocumentTypeSelect({ value, onChange }: DocumentTypeSelectProps) {
  const { data: types = [] } = useDocumentTypes();

  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => onChange(null)}
        className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
          value === null
            ? "border-primary bg-primary/10 text-primary"
            : "border-border text-muted-foreground hover:text-foreground"
        }`}
      >
        Sin tipo
      </button>
      {types.map((t) => {
        const IconCmp = (Icons as unknown as Record<string, LucideIcon>)[t.icon] ??
          Icons.FileText;
        const isActive = value === t.id;
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onChange(t.id)}
            className="px-2.5 py-1 rounded-md text-xs font-medium border transition-colors inline-flex items-center gap-1"
            style={{
              borderColor: isActive ? t.color : "var(--border)",
              backgroundColor: isActive ? `${t.color}1A` : undefined,
              color: isActive ? t.color : undefined,
            }}
          >
            <IconCmp className="h-3 w-3" />
            {t.name}
          </button>
        );
      })}
    </div>
  );
}
