"use client";

import {
  FilePlus, MessageSquare, UserCheck, ArrowRightLeft,
  Archive, Clipboard, Clock, Paperclip, AlertTriangle,
  Timer, FileText, Trash2, Edit2,
} from "lucide-react";
import { useCaseActivity, type ActivityEntry } from "@/hooks/useCases";
import { ArrowDown } from "lucide-react";
import { Spinner } from "@/components/atoms/Spinner";
import { Avatar } from "@/components/atoms/Avatar";
import { formatRelative } from "@/lib/utils";

const EVENT_CONFIG: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  "case.created":          { icon: FilePlus,        color: "text-emerald-600 bg-emerald-50 border-emerald-200",  label: "Caso creado" },
  "case.updated":          { icon: Edit2,           color: "text-blue-600 bg-blue-50 border-blue-200",           label: "Actualizado" },
  "case.status_changed":   { icon: ArrowRightLeft,  color: "text-violet-600 bg-violet-50 border-violet-200",     label: "Estado" },
  "case.assigned":         { icon: UserCheck,       color: "text-indigo-600 bg-indigo-50 border-indigo-200",     label: "Asignado" },
  "case.closed":           { icon: Archive,         color: "text-gray-600 bg-gray-50 border-gray-200",           label: "Cerrado" },
  "case.archived":         { icon: Archive,         color: "text-gray-600 bg-gray-50 border-gray-200",           label: "Archivado" },
  "case.restored":         { icon: FilePlus,        color: "text-emerald-600 bg-emerald-50 border-emerald-200",  label: "Restaurado" },
  "case.classified":       { icon: Clipboard,       color: "text-amber-600 bg-amber-50 border-amber-200",        label: "Clasificado" },
  "note.created":          { icon: FileText,        color: "text-blue-600 bg-blue-50 border-blue-200",           label: "Nota" },
  "chat.message.sent":     { icon: MessageSquare,   color: "text-cyan-600 bg-cyan-50 border-cyan-200",           label: "Mensaje" },
  "chat.message.edited":   { icon: Edit2,           color: "text-cyan-600 bg-cyan-50 border-cyan-200",           label: "Mensaje editado" },
  "chat.message.deleted":  { icon: Trash2,          color: "text-red-600 bg-red-50 border-red-200",              label: "Mensaje eliminado" },
  "timer.started":         { icon: Timer,           color: "text-green-600 bg-green-50 border-green-200",        label: "Timer iniciado" },
  "timer.stopped":         { icon: Clock,           color: "text-green-600 bg-green-50 border-green-200",        label: "Timer detenido" },
  "time_entry.manual_added": { icon: Clock,         color: "text-teal-600 bg-teal-50 border-teal-200",           label: "Tiempo manual" },
  "attachment.uploaded":   { icon: Paperclip,       color: "text-orange-600 bg-orange-50 border-orange-200",     label: "Adjunto" },
  "sla.breached":          { icon: AlertTriangle,   color: "text-red-600 bg-red-50 border-red-200",              label: "SLA vencido" },
  "resolution.requested":  { icon: Clock,           color: "text-blue-600 bg-blue-50 border-blue-200",           label: "Confirmación solicitada" },
  "resolution.responded":  { icon: Clipboard,       color: "text-emerald-600 bg-emerald-50 border-emerald-200",  label: "Confirmación respondida" },
};

function getConfig(eventType: string) {
  return EVENT_CONFIG[eventType] ?? {
    icon: FilePlus,
    color: "text-muted-foreground bg-muted border-border",
    label: eventType,
  };
}

function AssignmentCard({ entry }: { entry: ActivityEntry }) {
  const payload = entry.payload as {
    assigned_to?: string | null;
    assigned_to_name?: string | null;
    assigned_by_name?: string | null;
    from_assigned_to?: string | null;
    from_assigned_to_name?: string | null;
  };

  const toName = payload.assigned_to_name ?? (payload.assigned_to ? "Usuario" : null);
  const fromName = "from_assigned_to" in payload
    ? (payload.from_assigned_to_name ?? null)
    : undefined;
  const byName = payload.assigned_by_name;

  return (
    <div className="rounded-lg border border-indigo-200 bg-indigo-50 dark:bg-indigo-950/20 dark:border-indigo-800 p-3 mb-3">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900 border border-indigo-300 dark:border-indigo-700">
            <UserCheck className="h-3 w-3 text-indigo-600 dark:text-indigo-400" />
          </div>
          <span className="text-sm font-medium text-indigo-700 dark:text-indigo-300">
            Caso asignado
          </span>
        </div>
        <time className="text-xs text-muted-foreground">{formatRelative(entry.created_at)}</time>
      </div>

      <div className="pl-8 flex flex-col gap-1.5">
        {fromName !== undefined && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="text-xs font-medium w-8 shrink-0 text-right">De</span>
            <span className="italic">{fromName ?? "Sin asignar"}</span>
          </div>
        )}
        {fromName !== undefined && (
          <div className="pl-8">
            <ArrowDown className="h-3.5 w-3.5 text-indigo-400" />
          </div>
        )}
        <div className="flex items-center gap-2 text-sm">
          <span className="text-xs font-medium w-8 shrink-0 text-right text-indigo-600">A</span>
          {toName ? (
            <div className="flex items-center gap-1.5">
              <Avatar name={toName} size="xs" />
              <span className="font-medium text-foreground">{toName}</span>
            </div>
          ) : (
            <span className="text-muted-foreground italic">Sin asignar</span>
          )}
        </div>
        {byName && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
            <span className="w-8 shrink-0 text-right">Por</span>
            <span>{byName}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function ActivityItem({ entry }: { entry: ActivityEntry }) {
  if (entry.event_type === "case.assigned") {
    return <AssignmentCard entry={entry} />;
  }

  const cfg = getConfig(entry.event_type);
  const Icon = cfg.icon;
  const [bg, ...rest] = cfg.color.split(" ");
  const iconBg = rest.join(" ");

  return (
    <div className="flex gap-3 group">
      {/* Icon */}
      <div className={`mt-0.5 shrink-0 flex h-7 w-7 items-center justify-center rounded-full border ${iconBg}`}>
        <Icon className={`h-3.5 w-3.5 ${bg}`} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pb-4 border-b border-border last:border-0">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className="text-sm text-foreground leading-snug">{entry.description}</p>
            {entry.actor_name && (
              <div className="flex items-center gap-1.5 mt-1">
                <Avatar name={entry.actor_name} size="xs" />
                <span className="text-xs text-muted-foreground">{entry.actor_name}</span>
              </div>
            )}
          </div>
          <time className="shrink-0 text-xs text-muted-foreground whitespace-nowrap mt-0.5">
            {formatRelative(entry.created_at)}
          </time>
        </div>
      </div>
    </div>
  );
}

export function CaseActivity({ caseId }: { caseId: string }) {
  const { data: entries = [], isLoading } = useCaseActivity(caseId);

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-10 italic">
        Sin actividad registrada aún.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-0">
      {entries.map((entry) => (
        <ActivityItem key={entry.id} entry={entry} />
      ))}
    </div>
  );
}
