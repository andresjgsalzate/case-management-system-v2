"use client";

import { useQuery } from "@tanstack/react-query";
import { Zap, GitBranch, ToggleLeft, ToggleRight } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Badge } from "@/components/atoms/Badge";
import { Spinner } from "@/components/atoms/Spinner";
import { formatDate } from "@/lib/utils";
import type { ApiResponse } from "@/lib/types";

interface AutomationRule {
  id: string;
  name: string;
  description?: string;
  trigger_event: string;
  conditions: unknown[];
  actions: { type: string; params?: Record<string, unknown> }[];
  condition_logic: "AND" | "OR";
  is_active: boolean;
  execution_count: number;
  created_at: string;
}

function useAutomationRules() {
  return useQuery({
    queryKey: ["automation-rules"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<AutomationRule[]>>("/automation/rules");
      return data.data ?? [];
    },
  });
}

const EVENT_LABELS: Record<string, string> = {
  "case.created":          "Caso creado",
  "case.status_changed":   "Estado cambiado",
  "case.assigned":         "Caso asignado",
  "case.priority_changed": "Prioridad cambiada",
  "sla.breached":          "SLA incumplido",
};

export default function AutomationSettingsPage() {
  const { data: rules = [], isLoading } = useAutomationRules();

  return (
    <div className="flex flex-col gap-5 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Automatización</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isLoading ? "Cargando…" : `${rules.length} regla${rules.length !== 1 ? "s" : ""} configuradas`}
          </p>
        </div>
        <button
          type="button"
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Zap className="h-4 w-4" />
          Nueva regla
        </button>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      )}

      {!isLoading && rules.length === 0 && (
        <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
          <Zap className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p className="text-sm">No hay reglas de automatización</p>
          <p className="text-xs mt-1">Las reglas permiten ejecutar acciones automáticas ante eventos del sistema</p>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {rules.map((rule) => (
          <div
            key={rule.id}
            className="rounded-lg border border-border bg-card p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <div className="h-9 w-9 rounded-md bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                  <Zap className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-foreground">{rule.name}</span>
                    <Badge variant={rule.is_active ? "success" : "outline"} className="text-xs">
                      {rule.is_active ? "Activa" : "Inactiva"}
                    </Badge>
                  </div>
                  {rule.description && (
                    <p className="text-xs text-muted-foreground mt-0.5">{rule.description}</p>
                  )}
                </div>
              </div>
              <button type="button" className="text-muted-foreground hover:text-foreground transition-colors shrink-0">
                {rule.is_active
                  ? <ToggleRight className="h-5 w-5 text-primary" />
                  : <ToggleLeft className="h-5 w-5" />}
              </button>
            </div>

            <div className="mt-3 pt-3 border-t border-border flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <GitBranch className="h-3 w-3" />
                {EVENT_LABELS[rule.trigger_event] ?? rule.trigger_event}
              </span>
              <span>{rule.conditions.length} condición{rule.conditions.length !== 1 ? "es" : ""} ({rule.condition_logic})</span>
              <span>{rule.actions.length} acción{rule.actions.length !== 1 ? "es" : ""}</span>
              <span>{rule.execution_count} ejecuciones</span>
              <span>Creada {formatDate(rule.created_at)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
