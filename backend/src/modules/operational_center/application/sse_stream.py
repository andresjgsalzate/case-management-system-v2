"""Server-Sent Events generator for the dashboard live updates.

Phase 1 emits only `connected` + periodic `heartbeat` events. The
event-bus subscribe machinery (per-tenant queue with permission filter)
lands in a follow-up — the spec's pub/sub model isn't a direct fit for
the current fire-and-forget EventBus. Keeping this scaffolded so the
frontend hook can establish a connection today and start receiving real
events as soon as the subscribe contract firms up.
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import AsyncGenerator

# In-memory subscriber registry keyed by tenant_id. Each value is a list of
# asyncio.Queue references currently streaming for that tenant. Future
# `publish_to_dashboard(event)` can fan-out here without coupling to the
# existing EventBus shape.
_subscribers: dict[str, list[asyncio.Queue]] = {}

# Yield a heartbeat every 30s to keep proxies / browsers from closing the
# idle connection.
HEARTBEAT_SECONDS = 30


def _format_sse(event_type: str, payload: dict) -> str:
    """Encode one SSE message frame (`event:` + `data:` + blank line)."""
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def stream_dashboard_events(
    *, tenant_id: str,
) -> AsyncGenerator[str, None]:
    """Yields SSE-formatted strings for `tenant_id`.

    Yields an initial `connected` message, then loops with a 30s heartbeat
    timeout — if no real event arrives, the heartbeat fires.
    """
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
    _subscribers.setdefault(tenant_id, []).append(queue)

    yield _format_sse("connected", {"timestamp": _now_iso()})

    try:
        while True:
            try:
                event = await asyncio.wait_for(
                    queue.get(), timeout=HEARTBEAT_SECONDS,
                )
                yield _format_sse(
                    event.get("type", "message"),
                    event.get("payload", {}),
                )
            except asyncio.TimeoutError:
                yield _format_sse("heartbeat", {"timestamp": time.time()})
    finally:
        try:
            _subscribers.get(tenant_id, []).remove(queue)
        except ValueError:
            pass


async def publish_to_dashboard(
    *, tenant_id: str, event_type: str, payload: dict,
) -> int:
    """Fan-out helper called by other modules (or a future event_bus bridge).

    Returns the number of subscribers that received the event. Drops events
    silently if a subscriber's queue is full (back-pressure protection).
    """
    delivered = 0
    for queue in list(_subscribers.get(tenant_id, [])):
        try:
            queue.put_nowait({"type": event_type, "payload": payload})
            delivered += 1
        except asyncio.QueueFull:
            pass
    return delivered
