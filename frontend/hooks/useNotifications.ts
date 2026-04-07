import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
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
    refetchInterval: 30_000, // Poll every 30s as fallback
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
    refetchInterval: 15_000,
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

/** Optional: connect to SSE stream for real-time notifications */
export function useNotificationStream(onNotification?: (n: Notification) => void) {
  const qc = useQueryClient();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("access_token");
    if (!token) return;

    const source = new EventSource("/api/proxy/notifications/stream");

    source.onmessage = (event) => {
      try {
        const notif: Notification = JSON.parse(event.data);
        qc.invalidateQueries({ queryKey: [NOTIF_KEY] });
        onNotification?.(notif);
      } catch {
        // ignore malformed events
      }
    };

    source.onerror = () => source.close();

    return () => source.close();
  }, [qc, onNotification]);
}
