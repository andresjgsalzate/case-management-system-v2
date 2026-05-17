// SSE hook for Sub-spec 06 — Dashboard live stream.
// Reconnects with exponential backoff up to 30s; tracks staleness as the
// elapsed time since last heartbeat so the UI can show a "stream stalled"
// banner without dropping the connection.
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
  const sourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const lastHeartbeatRef = useRef<number>(Date.now());
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onEventRef = useRef(onEvent);

  // Keep latest callback in ref so we don't re-subscribe when caller passes
  // a new inline function each render.
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    function connect() {
      const source = new EventSource(
        "/api/v1/operational/dashboard/stream",
        { withCredentials: true },
      );
      sourceRef.current = source;

      source.addEventListener("connected", () => {
        setConnected(true);
        reconnectAttemptsRef.current = 0;
        lastHeartbeatRef.current = Date.now();
      });

      source.addEventListener("heartbeat", () => {
        lastHeartbeatRef.current = Date.now();
      });

      for (const type of KNOWN_EVENT_TYPES) {
        source.addEventListener(type, (e: MessageEvent) => {
          lastHeartbeatRef.current = Date.now();
          try {
            const payload = JSON.parse(e.data);
            onEventRef.current(type, payload);
          } catch {
            onEventRef.current(type, e.data);
          }
        });
      }

      source.onerror = () => {
        source.close();
        setConnected(false);
        const attempt = reconnectAttemptsRef.current;
        const delay = Math.min(30_000, 1000 * Math.pow(2, attempt));
        reconnectAttemptsRef.current = attempt + 1;
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    }

    connect();
    const staleInterval = setInterval(() => {
      setStaleMs(Date.now() - lastHeartbeatRef.current);
    }, 1000);

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      sourceRef.current?.close();
      clearInterval(staleInterval);
    };
  }, []);

  return { connected, staleMs };
}
