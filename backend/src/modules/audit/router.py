from fastapi import APIRouter, Depends, Query

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.audit.application.use_cases import AuditUseCases
from backend.src.modules.audit.infrastructure.models import AuditLogModel

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
AuditRead = Depends(PermissionChecker("audit", "read"))

_FK_FIELDS = {
    "status_id", "priority_id", "assigned_to", "team_id", "role_id",
    "category_id", "application_id", "origin_id", "created_by_id",
    "approved_by_id", "created_by",
}


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=SuccessResponse[list[dict]])
async def get_audit_logs(
    db: DBSession,
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: CurrentUser = AuditRead,
):
    uc = AuditUseCases(db=db)
    logs = await uc.list_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    actor_names, entity_labels = await uc.resolve_labels(logs)
    fk_values = await uc.resolve_fk_values(logs)
    return SuccessResponse.ok([
        _serialize(log, actor_names, entity_labels, fk_values) for log in logs
    ])


# ── Forensic: entity timeline ─────────────────────────────────────────────────

@router.get("/timeline/{entity_type}/{entity_id}", response_model=SuccessResponse[list[dict]])
async def get_entity_timeline(
    entity_type: str,
    entity_id: str,
    db: DBSession,
    current_user: CurrentUser = AuditRead,
):
    """All audit events for one entity in chronological order (oldest first)."""
    uc = AuditUseCases(db=db)
    logs = await uc.list_timeline(entity_type=entity_type, entity_id=entity_id)
    actor_names, entity_labels = await uc.resolve_labels(logs)
    fk_values = await uc.resolve_fk_values(logs)
    return SuccessResponse.ok([
        _serialize(log, actor_names, entity_labels, fk_values) for log in logs
    ])


# ── Forensic: correlated operation ───────────────────────────────────────────

@router.get("/operation/{correlation_id}", response_model=SuccessResponse[list[dict]])
async def get_operation_logs(
    correlation_id: str,
    db: DBSession,
    current_user: CurrentUser = AuditRead,
):
    """All audit events that share a correlation_id (same HTTP request)."""
    uc = AuditUseCases(db=db)
    logs = await uc.list_by_correlation(correlation_id=correlation_id)
    actor_names, entity_labels = await uc.resolve_labels(logs)
    fk_values = await uc.resolve_fk_values(logs)
    return SuccessResponse.ok([
        _serialize(log, actor_names, entity_labels, fk_values) for log in logs
    ])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _enrich_changes(changes: dict, fk_values: dict[str, str]) -> dict:
    """Replace UUID values in known FK fields with human-readable labels."""
    if not fk_values:
        return changes
    enriched: dict = {}
    for field, info in changes.items():
        if field == "_snapshot" and isinstance(info, dict):
            enriched["_snapshot"] = {
                k: (fk_values[str(v)] if k in _FK_FIELDS and isinstance(v, str) and v in fk_values else v)
                for k, v in info.items()
            }
        elif field in _FK_FIELDS and isinstance(info, dict):
            enriched[field] = {
                "old": fk_values.get(info["old"], info["old"]) if isinstance(info.get("old"), str) else info.get("old"),
                "new": fk_values.get(info["new"], info["new"]) if isinstance(info.get("new"), str) else info.get("new"),
            }
        else:
            enriched[field] = info
    return enriched


def _enrich_snapshot(snapshot: dict | None, fk_values: dict[str, str]) -> dict | None:
    """Replace UUID values in FK fields of a before_snapshot dict."""
    if not snapshot:
        return None
    if not fk_values:
        return snapshot
    return {
        k: (fk_values[str(v)] if k in _FK_FIELDS and isinstance(v, str) and v in fk_values else v)
        for k, v in snapshot.items()
    }


def _serialize(
    log: AuditLogModel,
    actor_names: dict[str, str],
    entity_labels: dict[str, str],
    fk_values: dict[str, str],
) -> dict:
    raw_changes = log.changes
    enriched_changes = _enrich_changes(raw_changes, fk_values) if raw_changes else None
    enriched_before = _enrich_snapshot(log.before_snapshot, fk_values)
    return {
        "id": log.id,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "entity_label": entity_labels.get(log.entity_id),
        "changes": enriched_changes,
        "before_snapshot": enriched_before,
        "actor_id": log.actor_id,
        "actor_name": actor_names.get(log.actor_id) if log.actor_id else None,
        "correlation_id": log.correlation_id,
        "user_agent": log.user_agent,
        "request_path": log.request_path,
        "ip_address": log.ip_address,
        "created_at": log.created_at.isoformat(),
    }
