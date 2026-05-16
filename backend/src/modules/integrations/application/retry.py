"""Retry backoff + failure handling for inbound events.

Backoff schedule (per spec §4.8): exponential 2 / 8 / 32 seconds for attempts
1 / 2 / 3. After `max_attempts` the inbound is moved to dead letter
(status='failed', next_retry_at=NULL) and an event is published so monitoring
(Sub-spec 06) can alert oncall.

`handle_processing_failure` does NOT re-raise — the caller decides whether
to surface the original exception. This function only updates the row and
the source's failure counter.
"""
from datetime import datetime, timedelta, timezone

from backend.src.core.events.base import BaseEvent


def compute_backoff_seconds(attempt: int) -> int:
    """attempt 1 → 2s, attempt 2 → 8s, attempt 3 → 32s.

    Formula `2 ** (1 + (attempt-1) * 2)` chosen so each retry waits roughly
    4× longer than the previous — long enough to outlast transient outages
    (Wazuh manager restart ~30s) without delaying recovery for real bugs.
    """
    return 2 ** (1 + (attempt - 1) * 2)


async def handle_processing_failure(
    db,
    inbound,
    source,
    error: Exception,
    events_bus=None,
) -> None:
    """Update `inbound` to reflect the failure: schedule a retry, or send it
    to the dead-letter queue when `attempt_count` reaches `max_attempts`.

    Always increments `source.total_events_failed` and stamps the truncated
    error string on `inbound.last_error`.
    """
    inbound.last_error = f"{type(error).__name__}: {str(error)[:1000]}"
    source.total_events_failed += 1

    if inbound.attempt_count >= inbound.max_attempts:
        inbound.status = "failed"
        inbound.next_retry_at = None
        if events_bus is not None:
            await events_bus.publish(BaseEvent(
                event_name="inbound_event.failed",
                tenant_id=inbound.tenant_id or "default",
                payload={
                    "inbound_id": inbound.id,
                    "source_id": inbound.source_id,
                    "error": inbound.last_error,
                },
            ))
    else:
        seconds = compute_backoff_seconds(inbound.attempt_count)
        inbound.status = "pending"
        inbound.next_retry_at = (
            datetime.now(timezone.utc) + timedelta(seconds=seconds)
        )

    await db.commit()
