"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  ChevronLeft, Clock, User, Tag, Calendar,
  ChevronDown, UserCheck, Archive, BarChart2, Layers,
} from "lucide-react";
import {
  useCase, useCaseStatuses, useTransitionCase,
  useArchiveCase, useUsers, useCaseSLA,
  useClassification,
  type CaseSLARecord,
} from "@/hooks/useCases";
import { StatusBadge } from "@/components/molecules/StatusBadge";
import { PriorityBadge } from "@/components/molecules/PriorityBadge";
import { Avatar } from "@/components/atoms/Avatar";
import { Spinner } from "@/components/atoms/Spinner";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import { CaseChat } from "@/components/organisms/CaseChat";
import { CaseNotes } from "@/components/organisms/CaseNotes";
import { CaseTimeTracker } from "@/components/organisms/CaseTimeTracker";
import { CaseClassification } from "@/components/organisms/CaseClassification";
import { CaseActivity } from "@/components/organisms/CaseActivity";
import { AssignCaseModal } from "@/components/organisms/AssignCaseModal";
import { getCurrentUserId } from "@/lib/apiClient";
import { formatDate, formatRelative } from "@/lib/utils";

type Tab = "details" | "notes" | "chat" | "tiempo" | "clasificacion" | "actividad";

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const confirm = useConfirm();
  const { data: c, isLoading, error } = useCase(params.id);
  const { data: statuses = [] } = useCaseStatuses();
  const { data: users = [] } = useUsers();
  const [tab, setTab] = useState<Tab>("details");
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const transition = useTransitionCase(params.id);
  const archive = useArchiveCase(params.id);
  const { data: sla } = useCaseSLA(params.id);
  const { data: classification } = useClassification(params.id);

  useEffect(() => {
    setCurrentUserId(getCurrentUserId());
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !c) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
        <p>Caso no encontrado.</p>
        <Link href="/cases" className="text-primary text-sm hover:underline">Volver a casos</Link>
      </div>
    );
  }

  // Show all statuses except the current one — backend validates allowed transitions
  const transitionTargets = statuses.filter(
    (s: { id: string; name: string; slug: string }) => s.id !== c.status_id
  );

  const assignedUser = users.find((u) => u.id === c.assigned_to);

  return (
    <div className="flex flex-col gap-5">
      {/* Back */}
      <Link
        href="/cases"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronLeft className="h-4 w-4" />
        Casos
      </Link>

      {/* Header card */}
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="font-mono text-xs text-muted-foreground">{c.case_number}</span>
              <StatusBadge status={c.status_name} />
              <PriorityBadge priority={c.priority_name} />
            </div>
            <h1 className="text-xl font-semibold text-foreground">{c.title}</h1>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Status transition */}
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button
                  disabled={transition.isPending}
                  className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-sm hover:bg-muted transition-colors disabled:opacity-50"
                >
                  Cambiar estado
                  <ChevronDown className="h-3.5 w-3.5" />
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  align="end"
                  sideOffset={4}
                  className="z-50 min-w-[11rem] rounded-md border border-border bg-card shadow-md py-1 animate-in fade-in-0 zoom-in-95"
                >
                  {transitionTargets.length === 0 ? (
                    <p className="px-3 py-2 text-xs text-muted-foreground">Sin transiciones disponibles</p>
                  ) : (
                    transitionTargets.map((s: { id: string; name: string }) => (
                      <DropdownMenu.Item
                        key={s.id}
                        onSelect={async () => {
                          try {
                            setActionError(null);
                            await transition.mutateAsync(s.id);
                          } catch (err: unknown) {
                            const e = err as { response?: { data?: { message?: string; detail?: string } } };
                            setActionError(e?.response?.data?.message ?? e?.response?.data?.detail ?? "Error al cambiar el estado");
                          }
                        }}
                        className="cursor-pointer px-3 py-2 text-sm text-foreground hover:bg-muted outline-none select-none"
                      >
                        {s.name}
                      </DropdownMenu.Item>
                    ))
                  )}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>

            {/* Assign */}
            <AssignCaseModal
              caseId={params.id}
              currentAssignedTo={c.assigned_to ?? null}
              currentTeamId={c.team_id ?? null}
              trigger={
                <button className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-sm hover:bg-muted transition-colors">
                  <UserCheck className="h-3.5 w-3.5" />
                  Asignar
                </button>
              }
            />

            {/* Archive */}
            {!c.is_archived && (
              <button
                onClick={async () => {
                  const ok = await confirm({ title: "¿Archivar caso?", description: "El caso pasará a estado archivado y no podrá modificarse." });
                  if (!ok) return;
                  await archive.mutateAsync();
                }}
                disabled={archive.isPending}
                title="Archivar caso"
                className="inline-flex items-center rounded-md border border-border bg-background p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
              >
                <Archive className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Action error banner */}
        {actionError && (
          <div className="mt-3 flex items-center justify-between gap-2 rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive">
            <span>{actionError}</span>
            <button onClick={() => setActionError(null)} className="shrink-0 text-destructive/70 hover:text-destructive">✕</button>
          </div>
        )}

        {/* Meta grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mt-5 pt-5 border-t border-border">
          <MetaItem icon={User} iconColor="text-blue-500" label="Asignado a">
            {assignedUser ? (
              <div className="flex items-center gap-1.5">
                <Avatar name={assignedUser.full_name} size="xs" />
                <span className="text-sm truncate">{assignedUser.full_name}</span>
              </div>
            ) : (
              <span className="text-sm text-muted-foreground italic">Sin asignar</span>
            )}
          </MetaItem>
          <MetaItem icon={BarChart2} iconColor="text-amber-500" label="Prioridad">
            <PriorityBadge priority={c.priority_name} />
          </MetaItem>
          <MetaItem icon={Layers} iconColor="text-purple-500" label="Clasificación">
            {classification ? (
              <span className={`text-xs font-bold px-2 py-0.5 rounded border ${
                classification.complexity_level === "alta"
                  ? "bg-red-100 text-red-800 border-red-200"
                  : classification.complexity_level === "media"
                  ? "bg-yellow-100 text-yellow-800 border-yellow-200"
                  : "bg-green-100 text-green-800 border-green-200"
              }`}>
                {classification.complexity_level?.toUpperCase()}
              </span>
            ) : (
              <span className="text-sm text-muted-foreground italic">Sin clasificar</span>
            )}
          </MetaItem>
          <MetaItem icon={Tag} iconColor="text-cyan-500" label="Aplicación">
            <span className="text-sm text-muted-foreground">{c.application_name ?? "N/A"}</span>
          </MetaItem>
          <MetaItem icon={Calendar} iconColor="text-emerald-500" label="Creado">
            <span className="text-sm text-muted-foreground">{formatDate(c.created_at)}</span>
          </MetaItem>
          <MetaItem icon={Clock} iconColor="text-indigo-400" label="Actualizado">
            <span className="text-sm text-muted-foreground">{formatRelative(c.updated_at)}</span>
          </MetaItem>
        </div>

        {/* SLA */}
        {sla && <SLAWidget sla={sla} />}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border gap-0">
        {(["details", "notes", "chat", "tiempo", "clasificacion", "actividad"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {{ details: "Detalles", notes: "Notas", chat: "Chat", tiempo: "Tiempo", clasificacion: "Clasificación", actividad: "Actividad" }[t]}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="rounded-lg border border-border bg-card p-5">
        {tab === "details" && (
          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-3">Descripción</h3>
            {c.description ? (
              <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{c.description}</p>
            ) : (
              <p className="text-sm text-muted-foreground italic">Sin descripción</p>
            )}
          </div>
        )}
        {tab === "notes" && <CaseNotes caseId={params.id} />}
        {tab === "chat" && currentUserId && (
          <CaseChat caseId={params.id} currentUserId={currentUserId} />
        )}
        {tab === "tiempo" && <CaseTimeTracker caseId={params.id} />}
        {tab === "clasificacion" && <CaseClassification caseId={params.id} />}
        {tab === "actividad" && <CaseActivity caseId={params.id} />}
      </div>
    </div>
  );
}

function MetaItem({
  icon: Icon,
  iconColor,
  label,
  children,
}: {
  icon: React.ElementType;
  iconColor?: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className={`h-3.5 w-3.5 ${iconColor ?? ""}`} />
        {label}
      </div>
      {children}
    </div>
  );
}

function SLAWidget({ sla }: { sla: CaseSLARecord }) {
  const now = Date.now();
  const target = new Date(sla.target_at).getTime();
  const started = new Date(sla.started_at).getTime();
  const total = target - started;
  const elapsed = now - started;
  const remaining = target - now;
  const pct = Math.min(100, Math.max(0, (elapsed / total) * 100));

  const isTimerPaused = !!sla.paused_at;
  const isStatusPaused = !!sla.status_paused_at;
  const isPaused = isTimerPaused || isStatusPaused;
  const breached = sla.is_breached || (!isPaused && remaining <= 0);
  const atRisk = !breached && !isPaused && pct >= 75;

  const pauseReason = isStatusPaused
    ? "Pausado — esperando respuesta del cliente"
    : isTimerPaused
    ? "Pausado — timer activo"
    : null;

  const barColor = breached ? "bg-red-500" : isPaused ? "bg-blue-400" : atRisk ? "bg-amber-500" : "bg-emerald-500";
  const textColor = breached ? "text-red-600" : isPaused ? "text-blue-600" : atRisk ? "text-amber-600" : "text-emerald-600";
  const bgColor = breached
    ? "bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-900"
    : isPaused
    ? "bg-blue-50 border-blue-200 dark:bg-blue-950/20 dark:border-blue-900"
    : atRisk
    ? "bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-900"
    : "bg-emerald-50 border-emerald-200 dark:bg-emerald-950/20 dark:border-emerald-900";

  function fmtRemaining(ms: number) {
    if (ms <= 0) return "Vencido";
    const h = Math.floor(ms / 3600000);
    const m = Math.floor((ms % 3600000) / 60000);
    if (h >= 48) return `${Math.floor(h / 24)}d restantes`;
    if (h >= 1) return `${h}h ${m}m restantes`;
    return `${m}m restantes`;
  }

  const statusLabel = breached
    ? "SLA incumplido"
    : isPaused
    ? "SLA pausado"
    : atRisk
    ? "SLA en riesgo"
    : "SLA en tiempo";

  const statusTime = breached
    ? `Venció ${formatRelative(sla.target_at)}`
    : isPaused
    ? (pauseReason ?? "Pausado")
    : fmtRemaining(remaining);

  return (
    <div className={`mt-4 rounded-lg border p-3 flex flex-col gap-2 ${bgColor}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <Clock className={`h-3.5 w-3.5 ${textColor}`} />
          <span className={`text-xs font-semibold ${textColor}`}>{statusLabel}</span>
        </div>
        <div className="text-xs text-muted-foreground">
          <span className={`font-medium ${textColor}`}>{statusTime}</span>
          <span className="ml-2 opacity-60">· Límite: {formatDate(sla.target_at)}</span>
        </div>
      </div>
      <div className="h-1.5 w-full rounded-full bg-black/10 dark:bg-white/10 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${isPaused ? pct : pct}%` }}
        />
      </div>
    </div>
  );
}
