import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { apiClient } from "@/lib/apiClient";
import type { Notification, ApiResponse } from "@/lib/types";

const NOTIF_KEY = "notifications";

export function useNotifications(unreadOnly = false) {
  return useQuery({
    queryKey: [NOTIF_KEY, unreadOnly],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Notification[]>>("/notifications", {
        params: { unread_only: unreadOnly },
      });
      return data.data ?? [];
    },
    refetchInterval: 8_000, // Poll every 8s as fallback when SSE is unavailable
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: [NOTIF_KEY, "unread-count"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<{ unread_count: number }>>(
        "/notifications/unread-count"
      );
      return data.data?.unread_count ?? 0;
    },
    refetchInterval: 8_000,
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.post(`/notifications/${id}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: [NOTIF_KEY] }),
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post("/notifications/read-all"),
    onSuccess: () => qc.invalidateQueries({ queryKey: [NOTIF_KEY] }),
  });
}

export function useDeleteNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/notifications/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: [NOTIF_KEY] }),
  });
}

export function useDeleteReadNotifications() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.delete("/notifications"),
    onSuccess: () => qc.invalidateQueries({ queryKey: [NOTIF_KEY] }),
  });
}

/**
 * SSE stream usando fetch (no EventSource) para poder enviar
 * el header Authorization que EventSource no soporta.
 * Reconecta automáticamente si el stream se cierra o falla.
 */
export function useNotificationStream(onNotification?: (n: Notification) => void) {
  const qc = useQueryClient();
  const onNotificationRef = useRef(onNotification);
  onNotificationRef.current = onNotification;

  useEffect(() => {
    if (typeof window === "undefined") return;

    let aborted = false;
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;
    let controller = new AbortController();

    async function connect() {
      const token = localStorage.getItem("access_token");
      if (!token || aborted) return;

      try {
        const res = await fetch("/api/notifications/stream", {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          // No reconectar en 401 (token inválido)
          if (res.status === 401) return;
          scheduleReconnect();
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (!aborted) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data:")) continue;
            try {
              const notif: Notification = JSON.parse(line.slice(5).trim());
              qc.invalidateQueries({ queryKey: [NOTIF_KEY] });
              onNotificationRef.current?.(notif);
            } catch {
              // ignore malformed events
            }
          }
        }
      } catch {
        // AbortError al desmontar — ignorar; otros errores: reconectar
      }

      if (!aborted) scheduleReconnect();
    }

    function scheduleReconnect() {
      retryTimeout = setTimeout(() => {
        controller = new AbortController();
        connect();
      }, 5_000);
    }

    connect();

    return () => {
      aborted = true;
      controller.abort();
      if (retryTimeout) clearTimeout(retryTimeout);
    };
  }, [qc]); // onNotification se lee via ref — no recrea el efecto
}
