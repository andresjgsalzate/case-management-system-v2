"use client";

import { useQuery } from "@tanstack/react-query";
import { Shield, ChevronRight } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { Badge } from "@/components/atoms/Badge";
import { formatDate } from "@/lib/utils";
import type { ApiResponse } from "@/lib/types";

interface Role {
  id: string;
  name: string;
  description?: string;
  permissions?: { id: string; module: string; action: string; scope: string }[];
  created_at: string;
}

function useRoles() {
  return useQuery({
    queryKey: ["roles"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Role[]>>("/roles");
      return data.data ?? [];
    },
  });
}

const ROLE_COLORS: Record<string, "default" | "warning" | "success" | "destructive" | "secondary" | "outline"> = {
  "Super Admin": "destructive",
  "Admin":       "warning",
  "Manager":     "default",
  "Agent":       "secondary",
};

export default function RolesSettingsPage() {
  const { data: roles = [], isLoading } = useRoles();

  return (
    <div className="flex flex-col gap-5 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Roles y Permisos</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {isLoading ? "Cargando…" : `${roles.length} rol${roles.length !== 1 ? "es" : ""} configurados`}
        </p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      )}

      <div className="flex flex-col gap-3">
        {roles.map((role) => {
          const permCount = role.permissions?.length ?? 0;
          const modules = [...new Set(role.permissions?.map((p) => p.module) ?? [])];
          return (
            <div
              key={role.id}
              className="rounded-lg border border-border bg-card p-4 hover:border-primary/30 transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-md bg-muted flex items-center justify-center shrink-0">
                    <Shield className="h-4.5 w-4.5 text-muted-foreground" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{role.name}</span>
                      <Badge variant={ROLE_COLORS[role.name] ?? "outline"} className="text-xs">
                        {role.name}
                      </Badge>
                    </div>
                    {role.description && (
                      <p className="text-xs text-muted-foreground mt-0.5">{role.description}</p>
                    )}
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground mt-1 shrink-0" />
              </div>

              <div className="mt-3 pt-3 border-t border-border flex items-center gap-4 text-xs text-muted-foreground">
                <span>{permCount} permiso{permCount !== 1 ? "s" : ""}</span>
                <span>{modules.length} módulo{modules.length !== 1 ? "s" : ""}</span>
                <span>Creado {formatDate(role.created_at)}</span>
              </div>

              {modules.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {modules.slice(0, 8).map((mod) => (
                    <span key={mod} className="px-1.5 py-0.5 rounded text-xs bg-muted text-muted-foreground capitalize">
                      {mod}
                    </span>
                  ))}
                  {modules.length > 8 && (
                    <span className="px-1.5 py-0.5 rounded text-xs bg-muted text-muted-foreground">
                      +{modules.length - 8} más
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
