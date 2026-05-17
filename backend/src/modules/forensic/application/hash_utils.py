"""SHA-256 canonical hashing for chain of custody.

A hunt's result is hashed over its canonical JSON encoding (sorted keys,
no whitespace, UTF-8). Same logical content always yields the same hash —
required so the digest persisted in ``forensic_hunts.result_hash`` and
``forensic_hunt_results.row_hash`` can be re-verified later regardless of
how the JSON happened to be serialised at write time.
"""
import hashlib
import json
from typing import Any


def sha256_canonical(obj: Any) -> str:
    """SHA-256 hex of ``obj`` rendered as canonical JSON.

    ``default=str`` lets non-JSON-native values (``datetime``, ``UUID``)
    pass through deterministically via ``str()``.
    """
    canonical = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """SHA-256 hex of raw bytes (for attachment blobs)."""
    return hashlib.sha256(data).hexdigest()
