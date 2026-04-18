"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  Clock, User, Tag, Calendar,
  ChevronDown, UserCheck, Archive, BarChart2, Layers,
  RotateCcw,
} from "lucide-react";
import {
  useCase, useCaseStatuses, useTransitionCase,
  useArchiveCase, useRestoreCase, useCaseSLA,
  useClassification, useResolutionFeedback,
  type CaseSLARecord, type ResolutionFeedback,
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
import { CaseAttachments } from "@/components/organisms/CaseAttachments";
import { RelatedKBArticlesSection } from "@/components/organisms/RelatedKBArticlesSection";
import { AssignCaseModal } from "@/components/organisms/AssignCaseModal";
import { useHasPermission } from "@/hooks/useHasPermission";
import { getCurrentUserId } from "@/lib/apiClient";
import { formatDate, formatRelative, parseSolution, serializeSolution, type SolutionData } from "@/lib/utils";
import type { CaseStatus } from "@/lib/types";

type Tab = "details" | "notes" | "chat" | "tiempo" | "clasificacion" | "actividad";

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const confirm = useConfirm();
  const pathname = usePathname();
  const fromArchive = pathname.startsWith("/archive");
  const { data: c, isLoading, error } = useCase(params.id);
  const { data: statuses = [] } = useCaseStatuses();
  const [tab, setTab] = useState<Tab>("details");
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [closingTarget, setClosingTarget] = useState<{ id: string; name: string } | null>(null);
  const [solutionData, setSolutionData] = useState<SolutionData>({ summary: "", root_cause: "", steps: "", prevention: "", kb_notes: "" });
  const [solutionErrors, setSolutionErrors] = useState<Partial<Record<keyof SolutionData, string>>>({});

  const transition = useTransitionCase(params.id);
  const archive = useArchiveCase(params.id);
  const restore = useRestoreCase(params.id);
  const { data: sla } = useCaseSLA(params.id);
  const { data: classification } = useClassification(params.id);
  const { data: resolutionFeedback } = useResolutionFeedback(params.id);

  // ── Permission checks — no role names, just capabilities ─────────────────────
  const canViewTimer    = useHasPermission("time_entries",  "read");
  const canClassify     = useHasPermission("classification", "read");
  const canAssign       = useHasPermission("cases", "assign");
  const canArchive      = useHasPermission("cases", "archive");
  const canViewSLA      = useHasPermission("sla",   "read");
  // "assign/all" → can reassign any case regardless of who currently holds it
  const canAssignAny    = useHasPermission("cases", "assign", "all");

  // Tabs available based on permissions
  const visibleTabs: { key: Tab; label: string }[] = [
    { key: "details",       label: "Detalles" },
    { key: "notes",         label: "Notas" },
    { key: "chat",          label: "Chat" },
    ...(canViewTimer  ? [{ key: "tiempo"       as Tab, label: "Tiempo" }]        : []),
    ...(canClassify   ? [{ key: "clasificacion" as Tab, label: "Clasificación" }] : []),
    { key: "actividad", label: "Actividad" },
  ];

  useEffect(() => {
    setCurrentUserId(getCurrentUserId());
  }, []);

  // If the current tab is no longer visible (permissions changed), reset to "details"
  useEffect(() => {
    const validKeys = visibleTabs.map((t) => t.key);
    if (!validKeys.includes(tab)) setTab("details");
  }, [canViewTimer, canClassify]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // Filter by allowed_transitions of the current status
  const currentStatus = statuses.find((s: CaseStatus) => s.id === c.status_id);
  const transitionTargets = statuses.filter((s: CaseStatus) =>
    currentStatus?.allowed_transitions?.includes(s.slug)
  );

  // ── Assignment-based action control ──────────────────────────────────────────
  // If the case is assigned to someone, only that person (or a user with
  // cases/assign/all) can change its state or reassign it.
  const caseAssignedToOther = !!c.assigned_to && c.assigned_to !== currentUserId;
  const canTakeActions = canAssignAny || !caseAssignedToOther;

  const assignedUserName = c.assigned_user_name ?? null;

  return (
    <div className="flex flex-col gap-5">
      {/* Archived banner */}
      {c.is_archived && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/50">
          <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
            <Archive className="h-4 w-4 shrink-0" />
            <span>
              Este caso está <strong>archivado</strong>
              {c.archived_at && <> · {formatRelative(c.archived_at)}</>}
            </span>
          </div>
          {canArchive && (
            <button
              onClick={async () => {
                const ok = await confirm({ title: "¿Restaurar caso?", description: "El caso volverá a la lista activa y podrá modificarse." });
                if (!ok) return;
                try {
                  setActionError(null);
                  await restore.mutateAsync();
                } catch (err: unknown) {
                  const e = err as { response?: { data?: { message?: string; detail?: string } } };
                  setActionError(e?.response?.data?.message ?? e?.response?.data?.detail ?? "Error al restaurar el caso");
                }
              }}
              disabled={restore.isPending}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 transition-colors disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              {restore.isPending ? "Restaurando…" : "Restaurar"}
            </button>
          )}
        </div>
      )}

      {/* Header card */}
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="font-mono text-xs text-muted-foreground">{c.case_number}</span>
              <StatusBadge status={c.status_name} pulse />
              <PriorityBadge priority={c.priority_name} />
            </div>
            <h1 className="text-xl font-semibold text-foreground">{c.title}</h1>
          </div>

          {/* Action buttons — hidden for archived cases */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Status transition */}
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button
                  disabled={transition.isPending || c.is_archived || !canTakeActions}
                  className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-sm hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  title={
                    c.is_archived
                      ? "No se puede cambiar el estado de un caso archivado"
                      : !canTakeActions
                      ? "Solo el agente asignado puede cambiar el estado"
                      : undefined
                  }
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
                    transitionTargets.map((s: { id: string; name: string; slug: string }) => (
                      <DropdownMenu.Item
                        key={s.id}
                        onSelect={() => {
                          if (s.slug === "closed") {
                            setSolutionData({ summary: "", root_cause: "", steps: "", prevention: "", kb_notes: "" });
                            setSolutionErrors({});
                            setClosingTarget(s);
                          } else {
                            (async () => {
                              try {
                                setActionError(null);
                                await transition.mutateAsync({ target_status_id: s.id });
                              } catch (err: unknown) {
                                const e = err as { response?: { data?: { message?: string; detail?: string } } };
                                setActionError(e?.response?.data?.message ?? e?.response?.data?.detail ?? "Error al cambiar el estado");
                              }
                            })();
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

            {/* Assign — only for users with cases/assign permission, and only when they can act */}
            {canAssign && !c.is_archived && canTakeActions && (
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
            )}

            {/* Archive — solo disponible en estado Cerrado y para usuarios con cases/archive */}
            {canArchive && !c.is_archived && c.status_slug === "closed" && (
              <button
                onClick={async () => {
                  const ok = await confirm({ title: "¿Archivar caso?", description: "El caso pasará a estado archivado y no podrá modificarse." });
                  if (!ok) return;
                  try {
                    setActionError(null);
                    await archive.mutateAsync();
                  } catch (err: unknown) {
                    const e = err as { response?: { data?: { message?: string; detail?: string } } };
                    setActionError(e?.response?.data?.message ?? e?.response?.data?.detail ?? "Error al archivar el caso");
                  }
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
            {assignedUserName ? (
              <div className="flex items-center gap-1.5">
                <Avatar name={assignedUserName} size="xs" />
                <span className="text-sm truncate">{assignedUserName}</span>
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

        {/* SLA — internal metric, only shown to resolvers and admins */}
        {sla && canViewSLA && <SLAWidget sla={sla} />}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border gap-0">
        {visibleTabs.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content — altura fija para que la tarjeta de cabecera siempre sea visible */}
      <div className="rounded-lg border border-border bg-card p-5 flex flex-col h-[calc(100vh-16rem)] overflow-hidden">
        {tab === "details" && (
          <div className="flex flex-col lg:flex-row gap-6 flex-1 min-h-0 lg:items-start">
            {/* Left — ~60%: description + attachments */}
            <div className="flex-1 lg:flex-[3] overflow-y-auto pr-2 lg:max-h-[calc(100vh-22rem)]">
              <div className="flex flex-col gap-6">
                {/* Descripción */}
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-3">Descripción</h3>
                  {c.description ? (
                    <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{c.description}</p>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">Sin descripción</p>
                  )}
                </div>

                {/* Solución confirmada por el solicitante — solo si aprobó */}
                {resolutionFeedback?.status === "accepted" && (
                  <ResolutionFeedbackCard feedback={resolutionFeedback} />
                )}

                {/* Solución documentada — solo si el caso fue cerrado, colapsada por defecto */}
                {c.solution_description && (
                  <SolutionCard raw={c.solution_description} />
                )}

                {/* Archivos adjuntos */}
                <CaseAttachments caseId={params.id} readonly={c.is_archived} />

                {/* Documentos KB relacionados */}
                <RelatedKBArticlesSection caseId={params.id} />
              </div>
            </div>

            {/* Right — ~40%: activity log with independent scroll */}
            <div className="lg:flex-[2] border-t lg:border-t-0 lg:border-l border-border pt-6 lg:pt-0 lg:pl-6">
              <h3 className="text-sm font-medium text-muted-foreground mb-4">Actividad</h3>
              <div className="overflow-y-auto max-h-[calc(100vh-22rem)] pr-1">
                <CaseActivity caseId={params.id} />
              </div>
            </div>
          </div>
        )}
        {tab === "notes" && (
          <div className="flex-1 overflow-y-auto min-h-0">
            <CaseNotes caseId={params.id} readonly={c.is_archived} />
          </div>
        )}
        {tab === "chat" && currentUserId && (
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <CaseChat
              caseId={params.id}
              currentUserId={currentUserId}
              createdBy={c.created_by}
              readonly={c.is_archived}
            />
          </div>
        )}
        {tab === "tiempo" && canViewTimer && (
          <div className="flex-1 overflow-y-auto min-h-0">
            <CaseTimeTracker caseId={params.id} readonly={c.is_archived} />
          </div>
        )}
        {tab === "clasificacion" && canClassify && (
          <div className="flex-1 overflow-y-auto min-h-0">
            <CaseClassification caseId={params.id} />
          </div>
        )}
        {tab === "actividad" && (
          <div className="flex-1 overflow-y-auto min-h-0">
            <CaseActivity caseId={params.id} />
          </div>
        )}
      </div>

      {/* Modal: formulario estructurado de solución al cerrar caso */}
      {closingTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
            {/* Header */}
            <div className="px-5 py-4 border-b border-border shrink-0">
              <p className="text-sm font-semibold text-foreground">Registrar solución para cerrar el caso</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Completa las preguntas clave — esta información ayudará a resolver casos similares en el futuro y a alimentar la base de conocimiento.
              </p>
            </div>

            {/* Form body */}
            <div className="px-5 py-4 flex flex-col gap-5 overflow-y-auto">
              <SolutionField
                label="Resumen de la solución"
                hint="¿Qué se hizo en concreto para resolver el caso? (1-3 oraciones)"
                required
                value={solutionData.summary}
                error={solutionErrors.summary}
                onChange={(v) => { setSolutionData((d) => ({ ...d, summary: v })); setSolutionErrors((e) => ({ ...e, summary: undefined })); }}
              />
              <SolutionField
                label="Causa raíz"
                hint="¿Por qué ocurrió el problema? ¿Qué lo originó?"
                required
                value={solutionData.root_cause}
                error={solutionErrors.root_cause}
                onChange={(v) => { setSolutionData((d) => ({ ...d, root_cause: v })); setSolutionErrors((e) => ({ ...e, root_cause: undefined })); }}
              />
              <SolutionField
                label="Pasos aplicados"
                hint="¿Qué acciones específicas se tomaron, paso a paso?"
                required
                value={solutionData.steps}
                error={solutionErrors.steps}
                onChange={(v) => { setSolutionData((d) => ({ ...d, steps: v })); setSolutionErrors((e) => ({ ...e, steps: undefined })); }}
              />
              <SolutionField
                label="Prevención"
                hint="¿Cómo se puede evitar que este problema vuelva a ocurrir?"
                value={solutionData.prevention ?? ""}
                onChange={(v) => setSolutionData((d) => ({ ...d, prevention: v }))}
              />
              <SolutionField
                label="Notas para base de conocimiento / IA"
                hint="¿Hay patrones, errores específicos, comandos o referencias útiles para documentar?"
                value={solutionData.kb_notes ?? ""}
                onChange={(v) => setSolutionData((d) => ({ ...d, kb_notes: v }))}
              />
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-border flex justify-end gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setClosingTarget(null)}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm hover:bg-muted transition-colors"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={transition.isPending}
                onClick={async () => {
                  const errors: typeof solutionErrors = {};
                  if (!solutionData.summary.trim()) errors.summary = "Requerido";
                  if (!solutionData.root_cause.trim()) errors.root_cause = "Requerido";
                  if (!solutionData.steps.trim()) errors.steps = "Requerido";
                  if (Object.keys(errors).length) { setSolutionErrors(errors); return; }
                  try {
                    setActionError(null);
                    await transition.mutateAsync({
                      target_status_id: closingTarget.id,
                      solution_description: serializeSolution({
                        summary: solutionData.summary.trim(),
                        root_cause: solutionData.root_cause.trim(),
                        steps: solutionData.steps.trim(),
                        prevention: solutionData.prevention?.trim() || undefined,
                        kb_notes: solutionData.kb_notes?.trim() || undefined,
                      }),
                    });
                    setClosingTarget(null);
                  } catch (err: unknown) {
                    const e = err as { response?: { data?: { message?: string; detail?: string } } };
                    setActionError(e?.response?.data?.message ?? e?.response?.data?.detail ?? "Error al cerrar el caso");
                    setClosingTarget(null);
                  }
                }}
                className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {transition.isPending ? "Cerrando…" : "Confirmar cierre"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── SolutionField ──────────────────────────────────────────────────────────────

function SolutionField({
  label,
  hint,
  required,
  value,
  error,
  onChange,
}: {
  label: string;
  hint: string;
  required?: boolean;
  value: string;
  error?: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-1">
        <label className="text-sm font-medium text-foreground">{label}</label>
        {required && <span className="text-destructive text-xs">*</span>}
      </div>
      <p className="text-xs text-muted-foreground">{hint}</p>
      <textarea
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none transition-colors ${
          error ? "border-destructive focus:ring-destructive/30" : "border-input"
        }`}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

// ── SolutionCard ───────────────────────────────────────────────────────────────

function SolutionCard({ raw }: { raw: string }) {
  const [open, setOpen] = useState(false);
  const data = parseSolution(raw);
  if (!data) return null;

  const isLegacy = !data.root_cause && !data.steps;

  if (isLegacy) {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 dark:border-emerald-900 dark:bg-emerald-950/20 overflow-hidden">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="w-full flex items-center gap-2 px-4 py-3 hover:bg-emerald-100/50 dark:hover:bg-emerald-900/30 transition-colors"
        >
          <div className="h-5 w-5 rounded-full bg-emerald-100 dark:bg-emerald-900 flex items-center justify-center shrink-0">
            <span className="text-emerald-600 dark:text-emerald-400 text-[10px]">✓</span>
          </div>
          <h3 className="text-sm font-semibold text-emerald-800 dark:text-emerald-300">Solución aplicada</h3>
          <ChevronDown className={`ml-auto h-4 w-4 text-emerald-600 dark:text-emerald-400 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
        {open && (
          <div className="px-4 pb-4 border-t border-emerald-200 dark:border-emerald-900 pt-3">
            <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">{data.summary}</p>
          </div>
        )}
      </div>
    );
  }

  const sections: { key: keyof typeof data; label: string; color: string }[] = [
    { key: "summary",    label: "Resumen",          color: "text-emerald-700 dark:text-emerald-400" },
    { key: "root_cause", label: "Causa raíz",        color: "text-amber-700 dark:text-amber-400" },
    { key: "steps",      label: "Pasos aplicados",   color: "text-blue-700 dark:text-blue-400" },
    { key: "prevention", label: "Prevención",         color: "text-violet-700 dark:text-violet-400" },
    { key: "kb_notes",   label: "Notas para KB / IA", color: "text-slate-600 dark:text-slate-400" },
  ];

  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50/40 dark:border-emerald-900 dark:bg-emerald-950/20 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-4 py-3 border-b border-emerald-200 dark:border-emerald-900 hover:bg-emerald-100/50 dark:hover:bg-emerald-900/30 transition-colors"
      >
        <div className="h-5 w-5 rounded-full bg-emerald-100 dark:bg-emerald-900 flex items-center justify-center shrink-0">
          <span className="text-emerald-600 dark:text-emerald-400 text-[10px]">✓</span>
        </div>
        <h3 className="text-sm font-semibold text-emerald-800 dark:text-emerald-300">Solución documentada</h3>
        <ChevronDown className={`ml-auto h-4 w-4 text-emerald-600 dark:text-emerald-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="divide-y divide-emerald-100 dark:divide-emerald-900/60">
          {sections.map(({ key, label, color }) => {
            const value = data[key];
            if (!value) return null;
            return (
              <div key={key} className="px-4 py-3 grid grid-cols-[140px_1fr] gap-3 items-start">
                <span className={`text-xs font-semibold uppercase tracking-wide ${color} mt-0.5`}>{label}</span>
                <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{value}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── ResolutionFeedbackCard ─────────────────────────────────────────────────────

function ResolutionFeedbackCard({ feedback }: { feedback: ResolutionFeedback }) {
  const [open, setOpen] = useState(true);
  const accepted = feedback.status === "accepted";

  const borderColor = accepted ? "border-blue-200 dark:border-blue-900" : "border-orange-200 dark:border-orange-900";
  const bgColor     = accepted ? "bg-blue-50/40 dark:bg-blue-950/20"    : "bg-orange-50/40 dark:bg-orange-950/20";
  const iconClass   = accepted ? "bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400"     : "bg-orange-100 dark:bg-orange-900 text-orange-600 dark:text-orange-400";
  const titleClass  = accepted ? "text-blue-800 dark:text-blue-300"     : "text-orange-800 dark:text-orange-300";
  const chevronClass = accepted ? "text-blue-500 dark:text-blue-400"    : "text-orange-500 dark:text-orange-400";
  const hoverClass  = accepted ? "hover:bg-blue-100/50 dark:hover:bg-blue-900/30" : "hover:bg-orange-100/50 dark:hover:bg-orange-900/30";

  return (
    <div className={`rounded-lg border overflow-hidden ${borderColor} ${bgColor}`}>
      {/* Header — colapsable */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`w-full flex items-center gap-2 px-4 py-3 border-b ${borderColor} ${hoverClass} transition-colors`}
      >
        <div className={`h-5 w-5 rounded-full flex items-center justify-center text-[10px] shrink-0 ${iconClass}`}>
          {accepted ? "★" : "✗"}
        </div>
        <h3 className={`text-sm font-semibold ${titleClass}`}>
          {accepted ? "Solución confirmada por el solicitante" : "Solución rechazada por el solicitante"}
        </h3>
        {feedback.responded_at && (
          <span className="text-xs text-muted-foreground">
            {formatRelative(feedback.responded_at)}
          </span>
        )}
        <ChevronDown className={`ml-auto h-4 w-4 shrink-0 transition-transform ${chevronClass} ${open ? "rotate-180" : ""}`} />
      </button>

      {/* Body */}
      {open && (
        <div className="px-4 py-3 flex flex-col gap-3">
          {accepted && feedback.rating && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground w-28 shrink-0">Calificación</span>
              <div className="flex items-center gap-0.5">
                {Array.from({ length: 5 }).map((_, i) => (
                  <svg
                    key={i}
                    className={`h-4 w-4 ${i < feedback.rating! ? "text-amber-400 fill-amber-400" : "text-muted-foreground/30"}`}
                    viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
                  </svg>
                ))}
                <span className="text-xs text-muted-foreground ml-1">{feedback.rating}/5</span>
              </div>
            </div>
          )}
          {feedback.observation && (
            <div className="flex gap-2 items-start">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground w-28 shrink-0 mt-0.5">Observación</span>
              <p className="text-sm text-foreground leading-relaxed">{feedback.observation}</p>
            </div>
          )}
          <div className="flex gap-2 items-center">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground w-28 shrink-0">Respondido por</span>
            <span className="text-sm text-foreground">{feedback.responded_by_name ?? "—"}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── MetaItem ───────────────────────────────────────────────────────────────────

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
