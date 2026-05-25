"""Build the immutable ``data_snapshot`` payload for ``case_generated_reports``.

Pure data-aggregation: this module reads from the DB + the in-memory case
object, returns a plain dict. Persistence of the snapshot (or its overflow
attachment) is the caller's responsibility — see Task 8 (`generate_report`).

The 1 MB cap is enforced via ``is_snapshot_too_large(snapshot)`` — callers
that detect overflow are expected to persist the full snapshot as a JSON
``CaseAttachment`` (``source='alert_report'`` when that column is wired)
and store ``{"truncated": True, "snapshot_attachment_id": ...,
"case_summary": ...}`` in ``case_generated_reports.data_snapshot``.
"""
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SNAPSHOT_SIZE_LIMIT = 1024 * 1024  # 1 MB


async def build_data_snapshot(db: AsyncSession, case) -> dict[str, Any]:
    """Aggregate every cross-spec data needed to reproduce the report."""
    # The SOC triage (if any) is the structured source of truth for the
    # narrative blocks. We fetch it once and let its fields take precedence
    # over the legacy free-text extractors (which remain as fallback for
    # cases triaged before this feature existed).
    triage = await _snapshot_triage(db, case.id)

    snapshot = {
        "case": _snapshot_case(case),
        "triage": triage,
        "priority_calculation": await _snapshot_priority_calc(db, case.id),
        "forensic_hunts": await _snapshot_forensic_hunts(db, case.id),
        "evidence_attachments": await _snapshot_evidence_attachments(
            db, case.id
        ),
        "notes_summary": await _snapshot_notes_summary(db, case.id),
        "activity_timeline": await _snapshot_activity(db, case.id, limit=100),
        "recommendations": (
            (triage or {}).get("recommendations")
            or await _extract_recommendations_note(db, case.id)
        ),
        "behavior_relation": (
            (triage or {}).get("behavior_narrative")
            or await _extract_behavior_note(db, case.id)
        ),
        "iocs": await _extract_iocs(db, case),
        "mitre_techniques": (
            getattr(case.taxonomy, "mitre_techniques", []) or []
            if getattr(case, "taxonomy", None)
            else []
        ),
    }
    return snapshot


# ── SOC triage projection (latest revision) ─────────────────────────

async def _snapshot_triage(db: AsyncSession, case_id: str) -> dict[str, Any] | None:
    """Latest triage revision with FK names resolved + impact derived.

    Returns None when the case was never triaged -- callers fall back to
    legacy free-text extractors. All names are resolved here so the
    immutable snapshot doesn't depend on later catalog edits.
    """
    from backend.src.modules.triage.infrastructure.models import (
        CaseTriageModel,
        TriageToolActionModel,
        TriageToolTypeModel,
    )
    from backend.src.modules.security_taxonomies.infrastructure.models import (
        SecurityTaxonomyModel,
    )

    stmt = (
        select(CaseTriageModel)
        .where(CaseTriageModel.case_id == case_id)
        .order_by(CaseTriageModel.version.desc())
        .limit(1)
    )
    t = (await db.execute(stmt)).scalar_one_or_none()
    if t is None:
        return None

    sub = await db.get(SecurityTaxonomyModel, t.sub_taxonomy_id)
    parent = (
        await db.get(SecurityTaxonomyModel, sub.parent_id)
        if sub and sub.parent_id else None
    )
    tool_type = (
        await db.get(TriageToolTypeModel, t.tool_type_id)
        if t.tool_type_id else None
    )
    tool_action = (
        await db.get(TriageToolActionModel, t.tool_action_id)
        if t.tool_action_id else None
    )

    # Impacto potencial = sub-taxonomy's internal/external impact picked
    # by the origin context (spec section 2.1).
    impacto = None
    if sub:
        impacto = (
            sub.internal_impact_context
            if t.context_origin_type == "origen_interno"
            else sub.external_impact_context
        )

    return {
        "version": t.version,
        "triaged_at": t.triaged_at.isoformat() if t.triaged_at else None,
        "sub_taxonomy_name": sub.name if sub else None,
        # When sub has no parent it IS the root classification.
        "parent_taxonomy_name": (
            parent.name if parent else (sub.name if sub else None)
        ),
        "alert_severity": t.alert_severity,
        "context_origin_type": t.context_origin_type,
        "context_origin_detail": t.context_origin_detail,
        "asset_criticality": t.asset_criticality,
        "impacto_potencial": impacto,
        "related_asset": t.related_asset,
        "tool_type_name": tool_type.name if tool_type else None,
        "tool_action_name": tool_action.name if tool_action else None,
        "alert_duration_seconds": t.alert_duration_seconds,
        "alert_repetitions": t.alert_repetitions,
        "analysis_narrative": t.analysis_narrative,
        "behavior_narrative": t.behavior_narrative,
        "recommendations": t.recommendations,
        "calculated_score": (
            float(t.calculated_score) if t.calculated_score is not None else None
        ),
        "calculated_sla_minutes": t.calculated_sla_minutes,
    }


def is_snapshot_too_large(snapshot: dict[str, Any]) -> bool:
    """Returns True if the JSON-encoded snapshot exceeds the size cap."""
    return len(json.dumps(snapshot, default=str)) > SNAPSHOT_SIZE_LIMIT


def serialize_snapshot(snapshot: dict[str, Any]) -> bytes:
    """Canonical UTF-8 bytes used when persisting overflow as attachment."""
    return json.dumps(snapshot, indent=2, default=str).encode("utf-8")


# ── case projection ─────────────────────────────────────────────────────

def _snapshot_case(case) -> dict[str, Any]:
    def _attr(obj, name, default=None):
        return getattr(obj, name, default) if obj is not None else default

    return {
        "id": case.id,
        "case_number": getattr(case, "case_number", None),
        "case_type": getattr(case, "case_type", None),
        "title": getattr(case, "title", None),
        "description": getattr(case, "description", None),
        "status_slug": _attr(getattr(case, "status", None), "slug"),
        "status_name": _attr(getattr(case, "status", None), "name"),
        "priority_slug": _attr(getattr(case, "priority", None), "slug"),
        "priority_name": _attr(getattr(case, "priority", None), "name"),
        "taxonomy_code": _attr(getattr(case, "taxonomy", None), "tuic_code"),
        "taxonomy_name": _attr(getattr(case, "taxonomy", None), "name"),
        "service_item_name": _attr(
            getattr(case, "service_item", None), "name"
        ),
        "team_name": _attr(getattr(case, "team", None), "name"),
        "tenant_name": _attr(getattr(case, "tenant", None), "name"),
        "created_at": (
            case.created_at.isoformat()
            if getattr(case, "created_at", None) is not None
            else None
        ),
        "closed_at": (
            case.closed_at.isoformat()
            if getattr(case, "closed_at", None) is not None
            else None
        ),
        "custom_values": getattr(case, "custom_values", None) or {},
        "tlp": _attr(getattr(case, "taxonomy", None), "tlp_default", "WHITE"),
    }


# ── prioritization ──────────────────────────────────────────────────────

async def _snapshot_priority_calc(db: AsyncSession, case_id: str):
    from backend.src.modules.prioritization.infrastructure.models import (
        CasePriorityCalculationModel,
    )
    stmt = (
        select(CasePriorityCalculationModel)
        .where(CasePriorityCalculationModel.case_id == case_id)
        .order_by(CasePriorityCalculationModel.calculated_at.desc())
        .limit(1)
    )
    calc = (await db.execute(stmt)).scalar_one_or_none()
    if not calc:
        return None
    return {
        "formula_id": calc.formula_id,
        "inputs": calc.inputs,
        "weighted_sum": float(calc.weighted_sum),
        "calculated_at": calc.calculated_at.isoformat(),
    }


# ── forensics (Sub-spec 07) ─────────────────────────────────────────────

async def _snapshot_forensic_hunts(db: AsyncSession, case_id: str):
    """Return completed forensic hunts for the case.

    Sub-spec 07's forensic module is imported lazily so this builder
    keeps working even in environments where the module is not yet
    deployed (catalog of plugins).
    """
    try:
        from backend.src.modules.forensic.infrastructure.models import (
            ForensicHuntModel,
        )
    except ImportError:
        return []
    stmt = (
        select(ForensicHuntModel)
        .where(
            ForensicHuntModel.case_id == case_id,
            ForensicHuntModel.status == "completed",
        )
        .order_by(ForensicHuntModel.completed_at.desc())
    )
    hunts = (await db.execute(stmt)).scalars().all()
    return [
        {
            "hunt_id": h.id,
            "artifact_name": h.artifact_name,
            "target_label": h.target_label,
            "status": h.status,
            "result_summary": h.result_summary,
            "result_hash": h.result_hash,
            "completed_at": (
                h.completed_at.isoformat() if h.completed_at else None
            ),
        }
        for h in hunts
    ]


# ── attachments ─────────────────────────────────────────────────────────

async def _snapshot_evidence_attachments(db: AsyncSession, case_id: str):
    """List user-uploaded attachments for the case.

    Note: this repo's ``CaseAttachmentModel`` does not yet expose
    ``sha256`` or ``source`` columns (spec assumes them). When those
    columns land, extend this projection.
    """
    from backend.src.modules.attachments.infrastructure.models import (
        CaseAttachmentModel,
    )
    stmt = (
        select(CaseAttachmentModel)
        .where(CaseAttachmentModel.case_id == case_id)
        .order_by(CaseAttachmentModel.id.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "attachment_id": a.id,
            "original_filename": a.original_filename,
            "mime_type": a.mime_type,
            "file_size": a.file_size,
        }
        for a in rows
    ]


# ── notes ───────────────────────────────────────────────────────────────

async def _snapshot_notes_summary(db: AsyncSession, case_id: str) -> str:
    """Concatenate non-deleted notes into a single text block."""
    from backend.src.modules.notes.infrastructure.models import (
        CaseNoteModel,
    )
    stmt = (
        select(CaseNoteModel)
        .where(
            CaseNoteModel.case_id == case_id,
            CaseNoteModel.is_deleted.is_(False),
        )
        .order_by(CaseNoteModel.created_at.asc())
    )
    notes = (await db.execute(stmt)).scalars().all()
    chunks = []
    for n in notes:
        ts = n.created_at.isoformat() if n.created_at else ""
        chunks.append(f"[{ts}] {n.content}")
    return "\n\n".join(chunks)


# ── activity timeline ───────────────────────────────────────────────────

async def _snapshot_activity(
    db: AsyncSession, case_id: str, *, limit: int = 100
):
    from backend.src.modules.activity.infrastructure.models import (
        ActivityEntryModel,
    )
    stmt = (
        select(ActivityEntryModel)
        .where(ActivityEntryModel.case_id == case_id)
        .order_by(ActivityEntryModel.created_at.desc())
        .limit(limit)
    )
    entries = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "description": e.description,
            "payload": e.payload or {},
            "actor_id": e.actor_id,
            "created_at": (
                e.created_at.isoformat() if e.created_at else None
            ),
        }
        for e in entries
    ]


# ── derived/extracted fields ────────────────────────────────────────────
#
# These extractors are intentionally lightweight stubs — the spec mentions
# a "recommendations" and "behavior_relation" field captured from
# specially-formatted case notes, but the repo currently has no such
# convention encoded. They return None until that contract is defined,
# and Task 8 falls back to template defaults. Wire-up will land alongside
# the renderer (Task 6) once the data convention is decided.

async def _extract_recommendations_note(
    db: AsyncSession, case_id: str
) -> str | None:
    return None


async def _extract_behavior_note(
    db: AsyncSession, case_id: str
) -> str | None:
    return None


async def _extract_iocs(db: AsyncSession, case) -> list[dict[str, Any]]:
    return []
