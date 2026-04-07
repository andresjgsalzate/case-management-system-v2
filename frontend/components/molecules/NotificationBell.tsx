"use client";

import { useState, useRef, useEffect } from "react";
import { Bell, Check, CheckCheck } from "lucide-react";
import { cn, formatRelative } from "@/lib/utils";
import { useNotifications, useUnreadCount, useMarkRead, useMarkAllRead } from "@/hooks/useNotifications";
import { Spinner } from "@/components/atoms/Spinner";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const { data: count = 0 } = useUnreadCount();
  const { data: notifications = [], isLoading } = useNotifications(false);
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "relative h-9 w-9 rounded-md flex items-center justify-center",
          "text-muted-foreground hover:text-foreground hover:bg-muted",
          "transition-colors duration-150"
        )}
      >
        <Bell className="h-4 w-4" />
        {count > 0 && (
          <span className="absolute top-1 right-1 h-4 w-4 rounded-full bg-destructive text-[10px] font-bold text-white flex items-center justify-center">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-50 w-80 rounded-lg border border-border bg-card shadow-lg overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <span className="text-sm font-semibold text-foreground">Notificaciones</span>
            {count > 0 && (
              <button
                type="button"
                onClick={() => markAllRead.mutate()}
                className="text-xs text-primary hover:underline flex items-center gap-1"
              >
                <CheckCheck className="h-3 w-3" />
                Marcar todo leído
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-80 overflow-y-auto divide-y divide-border">
            {isLoading && (
              <div className="flex justify-center py-6">
                <Spinner size="sm" />
              </div>
            )}
            {!isLoading && notifications.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">
                Sin notificaciones
              </p>
            )}
            {notifications.slice(0, 10).map((n) => (
              <div
                key={n.id}
                className={cn(
                  "px-4 py-3 flex gap-3 cursor-pointer hover:bg-muted/50 transition-colors",
                  !n.is_read && "bg-primary/5"
                )}
                onClick={() => !n.is_read && markRead.mutate(n.id)}
              >
                {!n.is_read && (
                  <div className="mt-1.5 h-2 w-2 rounded-full bg-primary shrink-0" />
                )}
                {n.is_read && <div className="mt-1.5 h-2 w-2 shrink-0" />}
                <div className="flex-1 min-w-0">
                  <p className={cn("text-sm font-medium truncate", n.is_read && "text-muted-foreground")}>
                    {n.title}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">{n.body}</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {formatRelative(n.created_at)}
                  </p>
                </div>
                {!n.is_read && (
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); markRead.mutate(n.id); }}
                    className="text-muted-foreground hover:text-foreground shrink-0 mt-1"
                  >
                    <Check className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
