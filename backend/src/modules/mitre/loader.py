"""Live MITRE ATT&CK catalog with Redis cache + bundled snapshot fallback.

Three sources, evaluated in order:

1. Redis cache `mitre:enterprise:techniques:v1` — 24 h TTL.
2. Live fetch from MITRE's CTI GitHub mirror (45 MB STIX bundle).
3. Bundled snapshot at `backend/data/mitre/techniques.json` — only kicks
   in when both Redis is empty AND the live fetch fails (MITRE outage,
   no internet at first boot, etc.).

Module name kept as `loader` so the router import path doesn't move;
content is the live catalog service.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from backend.src.core.redis_client import get_redis


logger = logging.getLogger(__name__)


SOURCE_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/"
    "enterprise-attack/enterprise-attack.json"
)

CACHE_KEY = "mitre:enterprise:techniques:v2"
CACHE_TTL_SECONDS = 24 * 60 * 60

BUNDLED_SNAPSHOT = (
    Path(__file__).resolve().parents[3] / "data" / "mitre" / "techniques.json"
)


# ─── STIX projection (kept aligned with refresh_mitre_attack.py) ──


def _extract_external_id(stix_obj: dict) -> str | None:
    for ref in stix_obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            ext_id = ref.get("external_id")
            if ext_id and ext_id.startswith("T"):
                return ext_id
    return None


def _extract_tactics(stix_obj: dict) -> list[str]:
    return sorted(
        {
            phase["phase_name"]
            for phase in stix_obj.get("kill_chain_phases", [])
            if phase.get("kill_chain_name") == "mitre-attack"
        }
    )


def _project_bundle(bundle: dict) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for obj in bundle.get("objects", []):
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        ext_id = _extract_external_id(obj)
        if not ext_id:
            continue
        out.append(
            {
                "id": ext_id,
                "name": obj.get("name", ""),
                "tactics": _extract_tactics(obj),
                "is_subtechnique": bool(obj.get("x_mitre_is_subtechnique")),
                # Filled in below once we have the full id -> name map.
                "parent_id": None,
                "parent_name": None,
            }
        )

    # MITRE encodes the parent->child relation in the dotted-id convention
    # (T1003 -> T1003.001). Materialise it as an explicit field so callers
    # don't have to re-derive it (and so the picker can show a hierarchy
    # without an extra lookup roundtrip).
    name_by_id = {t["id"]: t["name"] for t in out}
    for t in out:
        if t["is_subtechnique"] and "." in t["id"]:
            pid = t["id"].split(".", 1)[0]
            t["parent_id"] = pid
            t["parent_name"] = name_by_id.get(pid)

    out.sort(key=lambda r: (r["id"].split(".")[0], r["id"]))
    return out


# ─── Source resolution chain ─────────────────────────────────────


async def _fetch_live() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        response = await client.get(SOURCE_URL)
        response.raise_for_status()
    return _project_bundle(response.json())


def _load_bundled_fallback() -> list[dict[str, Any]]:
    if not BUNDLED_SNAPSHOT.exists():
        return []
    try:
        return json.loads(BUNDLED_SNAPSHOT.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error(f"Bundled MITRE snapshot is corrupt: {exc}")
        return []


async def get_all(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    """Return all MITRE techniques. Cache-first, live fallback, bundled last."""
    redis = get_redis()

    if not force_refresh:
        cached = await redis.get(CACHE_KEY)
        if cached:
            return json.loads(cached)

    try:
        data = await _fetch_live()
        await redis.set(CACHE_KEY, json.dumps(data), ex=CACHE_TTL_SECONDS)
        logger.info(
            f"MITRE catalog refreshed live: {len(data)} techniques cached for "
            f"{CACHE_TTL_SECONDS // 3600} h"
        )
        return data
    except Exception as exc:
        logger.warning(
            f"MITRE live fetch failed ({type(exc).__name__}: {exc}); "
            "falling back to bundled snapshot"
        )
        return _load_bundled_fallback()


# ─── Public read API used by the router ──────────────────────────


async def get_by_id(tid: str) -> dict[str, Any] | None:
    for t in await get_all():
        if t["id"] == tid:
            return t
    return None


async def search(query: str, *, limit: int = 50) -> list[dict[str, Any]]:
    """Substring search with deterministic 4-tier ranking.

    1. exact id match    e.g. "T1078" -> Valid Accounts
    2. id prefix         "T10"        -> T1003, T1005, ...
    3. name prefix       "credential" -> Credential Access, Credential Dumping
    4. name/id substring "phish"      -> Phishing, Spearphishing Attachment, ...
    """
    techniques = await get_all()
    q = (query or "").strip().lower()
    if not q:
        return techniques[:limit]

    exact: list[dict] = []
    id_prefix: list[dict] = []
    name_prefix: list[dict] = []
    name_sub: list[dict] = []

    for t in techniques:
        tid = t["id"].lower()
        name = t["name"].lower()
        if tid == q:
            exact.append(t)
        elif tid.startswith(q):
            id_prefix.append(t)
        elif name.startswith(q):
            name_prefix.append(t)
        elif q in name or q in tid:
            name_sub.append(t)

    return (exact + id_prefix + name_prefix + name_sub)[:limit]
