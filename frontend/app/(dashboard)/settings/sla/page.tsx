"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Clock, AlertTriangle, CheckCircle, Pause, Timer, Plus, Trash2 } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import type { ApiResponse } from "@/lib/types";
import {
  useSLAIntegrationConfig,
  useUpdateSLAIntegrationConfig,
  type SLAIntegrationConfig,
} from "@/hooks/useCases";

interface SLAPolicy {
  id: string;
  priority_id: string;
  priority?: { name: string; level: number; color: string };
  target_response_hours?: number;
  target_resolution_hours: number;
  is_active?: boolean;
}

interface Priority {
  id: string;
  name: string;
  level: number;
  color: string;
  is_active: boolean;
}

function useSLAPolicies() {
  return useQuery({
    queryKey: ["sla-policies"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<SLAPolicy[]>>("/sla/policies");
      return data.data ?? [];
    },
  });
}

function usePriorities() {
  return useQuery({
    queryKey: ["case-priorities"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Priority[]>>("/case-priorities");
      return data.data ?? [];
    },
  });
}

function hoursLabel(h: number) {
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  const rem = h % 24;
  return rem ? `${d}d ${rem}h` : `${d}d`;
}

const URGENCY_ICON: Record<number, typeof Clock> = {
  1: Clock,
  2: Clock,
  3: AlertTriangle,
  4: AlertTriangle,
};

function IntegrationConfigSection() {
  const { data: config, isLoading } = useSLAIntegrationConfig();
  const update = useUpdateSLAIntegrationConfig();

  const [form, setForm] = useState<SLAIntegrationConfig>({
    enabled: false,
    pause_on_timer: true,
    low_max_hours: null,
    medium_max_hours: null,
    high_max_hours: null,
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (config) setForm(config);
  }, [config]);

  async function handleSave() {
    await update.mutateAsync(form);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  if (isLoading) return <div className="flex justify-center py-6"><Spinner /></div>;

  return (
    <div className="rounded-lg border border-border bg-card p-5 flex flex-col gap-5">
      <div className="flex items-center gap-2">
        <Timer className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold text-foreground">Integración SLA + Tiempo</h2>
      </div>

      {/* Master toggle */}
      <label className="flex items-center justify-between gap-3 cursor-pointer">
        <div>
          <p className="text-sm font-medium text-foreground">Activar integración</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Permite pausar el SLA y limitar horas según complejidad del caso
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={form.enabled}
          onClick={() => setForm((f) => ({ ...f, enabled: !f.enabled }))}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
            form.enabled ? "bg-primary" : "bg-muted"
          }`}
        >
          <span
            className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
              form.enabled ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </label>

      {form.enabled && (
        <>
          {/* Pause on timer toggle */}
          <label className="flex items-center justify-between gap-3 cursor-pointer pl-4 border-l-2 border-border">
            <div className="flex items-center gap-2">
              <Pause className="h-3.5 w-3.5 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium text-foreground">Pausar SLA con timer activo</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  El SLA se pausa mientras el agente tiene un timer corriendo
                </p>
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={form.pause_on_timer}
              onClick={() => setForm((f) => ({ ...f, pause_on_timer: !f.pause_on_timer }))}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
                form.pause_on_timer ? "bg-primary" : "bg-muted"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
                  form.pause_on_timer ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </label>

          {/* Max hours per complexity */}
          <div className="pl-4 border-l-2 border-border flex flex-col gap-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Horas máximas por complejidad
            </p>
            <p className="text-xs text-muted-foreground -mt-2">
              Si se configura, el agente no podrá registrar más horas que el límite para cada nivel.
              Dejar vacío para no limitar.
            </p>
            {(
              [
                { key: "low_max_hours", label: "Complejidad BAJA", color: "text-emerald-600" },
                { key: "medium_max_hours", label: "Complejidad MEDIA", color: "text-amber-600" },
                { key: "high_max_hours", label: "Complejidad ALTA", color: "text-red-600" },
              ] as const
            ).map(({ key, label, color }) => (
              <div key={key} className="flex items-center gap-3">
                <label className={`text-sm font-medium w-44 shrink-0 ${color}`}>{label}</label>
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  placeholder="Sin límite"
                  value={form[key] ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      [key]: e.target.value === "" ? null : parseFloat(e.target.value),
                    }))
                  }
                  className="w-32 rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <span className="text-xs text-muted-foreground">horas</span>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="flex items-center gap-3 pt-1 border-t border-border">
        <button
          onClick={handleSave}
          disabled={update.isPending}
          className="px-4 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {update.isPending ? "Guardando…" : "Guardar configuración"}
        </button>
        {saved && (
          <span className="flex items-center gap-1 text-xs text-emerald-600">
            <CheckCircle className="h-3.5 w-3.5" />
            Guardado
          </span>
        )}
      </div>
    </div>
  );
}

export default function SLASettingsPage() {
  const confirm = useConfirm();
  const qc = useQueryClient();
  const { data: policies = [], isLoading } = useSLAPolicies();
  const { data: priorities = [] } = usePriorities();
  const [showPolicyForm, setShowPolicyForm] = useState(false);
  const [policyForm, setPolicyForm] = useState({ priority_id: "", target_resolution_hours: 24 });
  const [policyError, setPolicyError] = useState("");

  const createPolicyMutation = useMutation({
    mutationFn: (body: typeof policyForm) => apiClient.post("/sla/policies", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sla-policies"] });
      setShowPolicyForm(false);
      setPolicyForm({ priority_id: "", target_resolution_hours: 24 });
      setPolicyError("");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setPolicyError(msg ?? "Error al crear política");
    },
  });

  const deletePolicyMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/sla/policies/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sla-policies"] }),
  });

  async function handleDeletePolicy(id: string, name: string) {
    const ok = await confirm({ description: `¿Eliminar la política SLA para "${name}"?` });
    if (ok) deletePolicyMutation.mutate(id);
  }

  const existingPriorityIds = new Set(policies.map((p) => p.priority_id));
  const availablePriorities = priorities.filter((p) => p.is_active && !existingPriorityIds.has(p.id));

  const sorted = [...policies].sort(
    (a, b) => (a.priority?.level ?? 0) - (b.priority?.level ?? 0)
  );

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Configuración SLA</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Políticas de resolución e integración con tiempo de gestión
        </p>
      </div>

      {/* Integration config section */}
      <IntegrationConfigSection />

      {/* Policies */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-foreground">Políticas por prioridad</h2>
          {availablePriorities.length > 0 && (
            <button
              type="button"
              onClick={() => { setShowPolicyForm((v) => !v); setPolicyError(""); }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              Nueva política
            </button>
          )}
        </div>

        {showPolicyForm && (
          <div className="rounded-lg border border-primary/30 bg-card p-4 flex flex-col gap-3 mb-3">
            <p className="text-sm font-medium">Nueva política SLA</p>
            {policyError && <p className="text-xs text-destructive">{policyError}</p>}
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-foreground">Prioridad</label>
                <select
                  className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                  value={policyForm.priority_id}
                  onChange={(e) => setPolicyForm((f) => ({ ...f, priority_id: e.target.value }))}
                >
                  <option value="">Seleccionar…</option>
                  {availablePriorities.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-foreground">Horas de resolución</label>
                <input
                  type="number"
                  min={1}
                  step={0.5}
                  className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                  value={policyForm.target_resolution_hours}
                  onChange={(e) => setPolicyForm((f) => ({ ...f, target_resolution_hours: parseFloat(e.target.value) || 24 }))}
                />
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowPolicyForm(false)} className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground">Cancelar</button>
              <button
                type="button"
                disabled={!policyForm.priority_id || createPolicyMutation.isPending}
                onClick={() => createPolicyMutation.mutate(policyForm)}
                className="px-3 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {createPolicyMutation.isPending ? "Guardando…" : "Crear"}
              </button>
            </div>
          </div>
        )}

        {isLoading && (
          <div className="flex justify-center py-16"><Spinner size="lg" /></div>
        )}

        {!isLoading && policies.length === 0 && (
          <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
            <Clock className="h-8 w-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No hay políticas SLA configuradas</p>
          </div>
        )}

        <div className="flex flex-col gap-3">
          {sorted.map((policy) => {
            const Icon = URGENCY_ICON[policy.priority?.level ?? 1] ?? Clock;
            const color = policy.priority?.color ?? "#6B7280";
            const resH = policy.target_resolution_hours;
            const urgent = resH <= 4;

            return (
              <div
                key={policy.id}
                className="rounded-lg border border-border bg-card p-4 flex items-center gap-4 group"
              >
                <div
                  className="h-10 w-10 rounded-md flex items-center justify-center shrink-0"
                  style={{ backgroundColor: color + "20" }}
                >
                  <Icon className="h-5 w-5" style={{ color }} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">
                      {policy.priority?.name ?? "Sin prioridad"}
                    </span>
                    {urgent && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-destructive/10 text-destructive">
                        Urgente
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Resolución objetivo: <strong className="text-foreground">{hoursLabel(resH)}</strong>
                    {policy.target_response_hours && (
                      <> · Respuesta: <strong className="text-foreground">{hoursLabel(policy.target_response_hours)}</strong></>
                    )}
                  </p>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  {policy.is_active !== false ? (
                    <div className="flex items-center gap-1 text-xs">
                      <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                      <span className="text-green-600 dark:text-green-400">Activa</span>
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">Inactiva</span>
                  )}
                  <button
                    type="button"
                    onClick={() => handleDeletePolicy(policy.id, policy.priority?.name ?? "política")}
                    className="text-muted-foreground hover:text-destructive transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
