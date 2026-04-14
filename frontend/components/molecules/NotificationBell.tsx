"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Bell, Check, CheckCheck, X, Trash2,
  UserCheck, AlertTriangle, BookOpen, Zap, Info, Clock,
} from "lucide-react";
import { cn, formatRelative } from "@/lib/utils";
import {
  useNotifications, useUnreadCount,
  useMarkRead, useMarkAllRead,
  useDeleteNotification, useDeleteReadNotifications,
  useNotificationStream,
} from "@/hooks/useNotifications";
import { Spinner } from "@/components/atoms/Spinner";
import type { Notification } from "@/lib/types";

function resolveUrl(n: Notification): string | null {
  if (!n.reference_id || !n.reference_type) return null;
  if (n.reference_type === "case")    return `/cases/${n.reference_id}`;
  if (n.reference_type === "article") return `/kb/${n.reference_id}`;
  return null;
}

const TYPE_CONFIG: Record<string, { icon: React.ElementType; color: string }> = {
  case_assigned:      { icon: UserCheck,     color: "text-blue-500" },
  case_updated:       { icon: Info,          color: "text-slate-400" },
  sla_breach:         { icon: Clock,         color: "text-red-500" },
  kb_review_request:  { icon: BookOpen,      color: "text-emerald-500" },
  mention:            { icon: Info,          color: "text-violet-500" },
  automation:         { icon: Zap,           color: "text-yellow-500" },
  info:               { icon: Info,          color: "text-slate-400" },
};

function NotifIcon({ type }: { type: string }) {
  const cfg = TYPE_CONFIG[type] ?? TYPE_CONFIG.info;
  const Icon = cfg.icon;
  return <Icon className={cn("h-4 w-4 shrink-0 mt-0.5", cfg.color)} />;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const { data: count = 0 } = useUnreadCount();
  const { data: notifications = [], isLoading } = useNotifications(false);
  const markRead     = useMarkRead();
  const markAllRead  = useMarkAllRead();
  const deleteOne    = useDeleteNotification();
  const deleteRead   = useDeleteReadNotifications();

  async function handleNotifClick(n: Notification) {
    if (!n.is_read) markRead.mutate(n.id);
    const url = resolveUrl(n);
    if (url) {
      setOpen(false);
      router.push(url);
    }
  }

  // SSE: recibe notificaciones en tiempo real e invalida la query
  useNotificationStream();

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const hasRead = notifications.some((n) => n.is_read);

  return (
    <div className="relative" ref={ref}>
      {/* Botón campana */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "relative h-9 w-9 rounded-md flex items-center justify-center",
          "text-muted-foreground hover:text-foreground hover:bg-muted transition-colors duration-150"
        )}
      >
        <Bell className="h-4 w-4 text-blue-500" />
        {count > 0 && (
          <span className="absolute top-1 right-1 h-4 w-4 rounded-full bg-destructive text-[10px] font-bold text-white flex items-center justify-center leading-none">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-50 w-80 rounded-lg border border-border bg-card shadow-lg overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <span className="text-sm font-semibold text-foreground">
              Notificaciones
              {count > 0 && (
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  {count} sin leer
                </span>
              )}
            </span>
            <div className="flex items-center gap-2">
              {count > 0 && (
                <button
                  type="button"
                  onClick={() => markAllRead.mutate()}
                  className="text-xs text-primary hover:underline flex items-center gap-1"
                  title="Marcar todo como leído"
                >
                  <CheckCheck className="h-3 w-3" />
                  Todo leído
                </button>
              )}
              {hasRead && (
                <button
                  type="button"
                  onClick={() => deleteRead.mutate()}
                  className="text-xs text-muted-foreground hover:text-destructive flex items-center gap-1 transition-colors"
                  title="Eliminar leídas"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>

          {/* Lista */}
          <div className="max-h-96 overflow-y-auto divide-y divide-border">
            {isLoading && (
              <div className="flex justify-center py-6">
                <Spinner size="sm" />
              </div>
            )}
            {!isLoading && notifications.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-10 text-muted-foreground">
                <Bell className="h-8 w-8 opacity-20" />
                <p className="text-sm">Sin notificaciones</p>
              </div>
            )}
            {notifications.slice(0, 15).map((n: Notification) => {
              const url = resolveUrl(n);
              return (
              <div
                key={n.id}
                className={cn(
                  "px-4 py-3 flex gap-3 group/item transition-colors relative",
                  (url || !n.is_read) ? "cursor-pointer" : "",
                  !n.is_read
                    ? "bg-primary/5 hover:bg-primary/10"
                    : "hover:bg-muted/40"
                )}
                onClick={() => handleNotifClick(n)}
              >
                <NotifIcon type={n.notification_type} />

                <div className="flex-1 min-w-0">
                  <p className={cn(
                    "text-sm font-medium truncate",
                    n.is_read && "text-muted-foreground font-normal"
                  )}>
                    {n.title}
                  </p>
                  <p className="text-xs text-muted-foreground line-clamp-2">{n.body}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <p className="text-[10px] text-muted-foreground">
                      {formatRelative(n.created_at)}
                    </p>
                    {url && (
                      <span className="text-[10px] text-primary/70 font-medium">
                        Ver →
                      </span>
                    )}
                  </div>
                </div>

                {/* Acciones inline */}
                <div className="flex flex-col gap-1 opacity-0 group-hover/item:opacity-100 transition-opacity shrink-0">
                  {!n.is_read && (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); markRead.mutate(n.id); }}
                      className="text-muted-foreground hover:text-primary transition-colors"
                      title="Marcar como leída"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); deleteOne.mutate(n.id); }}
                    className="text-muted-foreground hover:text-destructive transition-colors"
                    title="Eliminar"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>

                {/* Punto indicador no leída */}
                {!n.is_read && (
                  <div className="absolute left-2 mt-2 h-1.5 w-1.5 rounded-full bg-primary" />
                )}
              </div>
            );})}
          </div>
        </div>
      )}
    </div>
  );
}
