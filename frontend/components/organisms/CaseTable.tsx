"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { cn, formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/molecules/StatusBadge";
import { PriorityBadge } from "@/components/molecules/PriorityBadge";
import { Avatar } from "@/components/atoms/Avatar";
import { Spinner } from "@/components/atoms/Spinner";
import type { Case } from "@/lib/types";

interface CaseTableProps {
  cases: Case[];
  isLoading?: boolean;
  className?: string;
}

export function CaseTable({ cases, isLoading, className }: CaseTableProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!cases.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <p className="text-sm">No hay casos que mostrar</p>
      </div>
    );
  }

  return (
    <div className={cn("w-full overflow-x-auto", className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {["Caso", "Título", "Estado", "Prioridad", "Asignado a", "Creado"].map((col) => (
              <th
                key={col}
                className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap"
              >
                {col}
              </th>
            ))}
            <th className="px-4 py-3 w-10" />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {cases.map((c) => (
            <tr
              key={c.id}
              className="hover:bg-muted/40 transition-colors duration-100 group"
            >
              <td className="px-4 py-3 whitespace-nowrap">
                <span className="font-mono text-xs text-muted-foreground">
                  {c.case_number}
                </span>
              </td>
              <td className="px-4 py-3 max-w-64">
                <Link
                  href={`/cases/${c.id}`}
                  className="font-medium text-foreground hover:text-primary transition-colors truncate block"
                >
                  {c.title}
                </Link>
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
                {c.status ? (
                  <StatusBadge status={c.status.name} />
                ) : (
                  <StatusBadge status={c.status_id} />
                )}
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
                {c.priority ? (
                  <PriorityBadge priority={c.priority.name} />
                ) : (
                  <PriorityBadge priority={c.priority_id} />
                )}
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
                {c.assigned_user ? (
                  <div className="flex items-center gap-2">
                    <Avatar name={c.assigned_user.full_name} size="xs" />
                    <span className="text-sm text-muted-foreground truncate max-w-24">
                      {c.assigned_user.full_name}
                    </span>
                  </div>
                ) : (
                  <span className="text-xs text-muted-foreground italic">Sin asignar</span>
                )}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-xs text-muted-foreground">
                {formatDate(c.created_at)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
                <Link
                  href={`/cases/${c.id}`}
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
                >
                  <ExternalLink className="h-4 w-4" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
