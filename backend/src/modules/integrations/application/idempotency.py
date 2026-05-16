"""Idempotency key calculation per source_type + in-memory rate limiting.

The idempotency key is the SHA256 of `source_id + canonical_payload_subset`.
Each vendor has its own canonical subset — for Wazuh, the unique signal of an
alert is (event id, rule id, agent id, timestamp); re-deliveries that change
`full_log` text or pretty-print whitespace must still dedupe.

Rate limiting is a sliding-window counter held in process memory, guarded by
a single Lock. For multi-worker production this should be swapped for a Redis
backend (left as a follow-up).
"""
import hashlib
import json
import time
from collections import defaultdict
from threading import Lock


def calculate_idempotency_key(source, payload: dict) -> str:
    """Return a stable SHA256 hex key uniquely identifying `payload` from `source`."""
    if source.source_type == "wazuh":
        canonical = {
            "wazuh_event_id": payload.get("id"),
            "rule_id": (payload.get("rule") or {}).get("id"),
            "agent_id": (payload.get("agent") or {}).get("id"),
            "timestamp": payload.get("timestamp"),
        }
    elif source.source_type == "splunk":
        canonical = {
            "splunk_sid": payload.get("sid"),
            "_time": payload.get("_time"),
        }
    elif source.source_type == "sentinel":
        obj = payload.get("object") or {}
        canonical = {
            "incident_id": obj.get("id"),
            "modified_time": (obj.get("properties") or {}).get("modifiedTimeUtc"),
        }
    else:
        # crowdstrike / qradar / custom: hash the full payload — caller can override
        # later by promoting their source_type into the dispatch above.
        canonical = payload

    canonical_json = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(
        f"{source.id}:{canonical_json}".encode("utf-8"),
    ).hexdigest()


# ── Sliding-window rate limiter (in-memory) ──────────────────────────

class RateLimitExceededError(Exception):
    """Raised by check_rate_limit when a source crosses its per-minute quota."""


_rate_buckets: dict[str, list[float]] = defaultdict(list)
_rate_lock = Lock()


def check_rate_limit(source_id: str, limit_per_minute: int) -> None:
    """Raise RateLimitExceededError if `source_id` has had ≥limit hits in the past 60s.

    Records a successful call before returning (so repeated calls advance the window).
    """
    now = time.time()
    cutoff = now - 60
    with _rate_lock:
        bucket = _rate_buckets[source_id]
        bucket[:] = [t for t in bucket if t > cutoff]
        if len(bucket) >= limit_per_minute:
            raise RateLimitExceededError(
                f"Source {source_id} exceeded {limit_per_minute}/min",
            )
        bucket.append(now)


def reset_rate_limit_for_source(source_id: str) -> None:
    """Clear the bucket for `source_id`. Intended for tests and operator overrides."""
    with _rate_lock:
        _rate_buckets.pop(source_id, None)
