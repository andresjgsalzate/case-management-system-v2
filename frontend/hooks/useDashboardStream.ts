// SSE hook for Sub-spec 06 — Dashboard live stream.
// Reconnects with exponential backoff up to 30s; tracks staleness as the
// elapsed time since last heartbeat so the UI can show a "stream stalled"
// banner without dropping the connection.
//
// We use `fetch` + a manual SSE parser instead of the native EventSource
// because the latter has no way to attach an Authorization header --
// PermissionChecker on the backend requires Bearer auth, so EventSource
// would always 401. The notifications stream uses the same trick.
import { useEffect, useRef, useState } from "react";

const KNOWN_EVENT_TYPES = [
  "case.created",
  "case.updated",
  "case.priority_changed",
  "case.status_changed",
  "case.promoted",
  "approval.requested",
  "approval.decided",
  "playbook_run.started",
  "playbook_run.completed",
  "playbook_run.failed",
  "integration_health.degraded",
  "integration_health.recovered",
  "inbound_event.failed",
] as const;

export type DashboardEventHandler = (
  eventType: string,
  payload: unknown,
) => void;

export interface DashboardStreamState {
  connected: boolean;
  /** Milliseconds since last heartbeat — high values mean the stream stalled. */
  staleMs: number;
}

export function useDashboardStream(
  onEvent: DashboardEventHandler,
): DashboardStreamState {
  const [connected, setConnected] = useState(false);
  const [staleMs, setStaleMs] = useState(0);
  const reconnectAttemptsRef = useRef(0);
  const lastHeartbeatRef = useRef<number>(Date.now());
  const onEventRef = useRef(onEvent);

  // Keep latest callback in ref so we don't re-subscribe when caller passes
  // a new inline function each render.
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    let aborted = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let controller = new AbortController();

    function scheduleReconnect() {
      const attempt = reconnectAttemptsRef.current;
      const delay = Math.min(30_000, 1000 * Math.pow(2, attempt));
      reconnectAttemptsRef.current = attempt + 1;
      reconnectTimer = setTimeout(() => {
        controller = new AbortController();
        connect();
      }, delay);
    }

    function dispatch(eventType: string | null, dataLines: string[]) {
      if (!eventType) return;
      lastHeartbeatRef.current = Date.now();
      if (eventType === "connected") {
        setConnected(true);
        reconnectAttemptsRef.current = 0;
        return;
      }
      if (eventType === "heartbeat") return;
      if (!(KNOWN_EVENT_TYPES as readonly string[]).includes(eventType)) return;
      const raw = dataLines.join("\n");
      try {
        onEventRef.current(eventType, JSON.parse(raw));
      } catch {
        onEventRef.current(eventType, raw);
      }
    }

    async function connect() {
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("access_token")
          : null;
      if (!token || aborted) return;

      try {
        const res = await fetch("/api/v1/operational/dashboard/stream", {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
        if (!res.ok || !res.body) {
          // 401 = bad / expired token; don't reconnect in a tight loop.
          if (res.status === 401) return;
          if (!aborted) scheduleReconnect();
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let currentEvent: string | null = null;
        let currentData: string[] = [];

        while (!aborted) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          // SSE frames end on a blank line. Split on \n; the last fragment
          // is the still-unfinished line we keep for the next chunk.
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line === "") {
              dispatch(currentEvent, currentData);
              currentEvent = null;
              currentData = [];
            } else if (line.startsWith("event:")) {
              currentEvent = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              currentData.push(line.slice(5).trim());
            }
            // SSE spec also has `id:`, `retry:`, comments (`:foo`).
            // We ignore them -- not used by the backend dashboard stream.
          }
        }
      } catch {
        // Abort on unmount throws — fall through.
      }

      setConnected(false);
      if (!aborted) scheduleReconnect();
    }

    connect();
    const staleInterval = setInterval(() => {
      setStaleMs(Date.now() - lastHeartbeatRef.current);
    }, 1000);

    return () => {
      aborted = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      controller.abort();
      clearInterval(staleInterval);
    };
  }, []);

  return { connected, staleMs };
}
