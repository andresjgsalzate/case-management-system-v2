"""HTTP router for the security_taxonomies module.

Endpoints follow Sub-spec 02 §6.1. Permission gating uses PermissionChecker
FastAPI dependency. Use cases handle contextual permission (manage_global vs
create, tenant match) internally.

Not included in this MVP: export/import (Phase 2 TODO — large feature, has
no upstream consumer yet).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from backend.src.core.dependencies import DBSession
from backend.src.core.exceptions import NotFoundError
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.core.responses import SuccessResponse
from backend.src.modules.security_taxonomies.application.dtos import (
    CatalogMappingCreatePayload,
    NotificationCreatePayload,
    TaxonomyCreatePayload,
    TaxonomyResponse,
    TaxonomyUpdatePayload,
)
from backend.src.modules.security_taxonomies.application.use_cases import (
    SecurityTaxonomyUseCases,
)

router = APIRouter(prefix="/api/v1/security-taxonomies", tags=["security-taxonomies"])

# Permission dependencies (one per action used by router endpoints)
Read = Depends(PermissionChecker("security_taxonomies", "read"))
Create = Depends(PermissionChecker("security_taxonomies", "create"))
Update = Depends(PermissionChecker("security_taxonomies", "update"))
Delete = Depends(PermissionChecker("security_taxonomies", "delete"))
Audit = Depends(PermissionChecker("security_taxonomies", "read_audit_log"))


# ── Request DTOs not shared with application layer ──────────────────────

class _DeleteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str


class _ForkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_tenant_id: str


# ── List / tree / detail ────────────────────────────────────────────────

@router.get("", response_model=SuccessResponse[list[TaxonomyResponse]])
async def list_taxonomies(
    db: DBSession,
    parent_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    current_user: CurrentUser = Read,
):
    uc = SecurityTaxonomyUseCases(db=db)
    rows = await uc.list_taxonomies(
        tenant_id=current_user.tenant_id,
        parent_id=parent_id, search=search, include_inactive=include_inactive,
    )
    return SuccessResponse.ok([TaxonomyResponse.model_validate(r) for r in rows])


@router.get("/tree", response_model=SuccessResponse[list[dict]])
async def list_taxonomies_tree(
    db: DBSession,
    include_inactive: bool = Query(default=False),
    current_user: CurrentUser = Read,
):
    """Return taxonomies nested by parent_id (roots → children → grandchildren)."""
    uc = SecurityTaxonomyUseCases(db=db)
    all_rows = await uc.list_taxonomies(
        tenant_id=current_user.tenant_id,
        include_inactive=include_inactive,
    )

    by_parent: dict[str | None, list] = {}
    nodes_by_id: dict[str, dict] = {}
    for row in all_rows:
        node = TaxonomyResponse.model_validate(row).model_dump(mode="json")
        node["children"] = []
        nodes_by_id[row.id] = node
        by_parent.setdefault(row.parent_id, []).append(node)

    # Wire parents → children (only for nodes whose parent is visible)
    roots: list[dict] = []
    for parent_id_key, children in by_parent.items():
        if parent_id_key is None:
            roots.extend(children)
        elif parent_id_key in nodes_by_id:
            nodes_by_id[parent_id_key]["children"].extend(children)
        else:
            # Parent not visible to this tenant — treat orphaned child as a root
            roots.extend(children)
    return SuccessResponse.ok(roots)


@router.get("/{taxonomy_id}", response_model=SuccessResponse[TaxonomyResponse])
async def get_taxonomy(
    taxonomy_id: str,
    db: DBSession,
    current_user: CurrentUser = Read,
):
    uc = SecurityTaxonomyUseCases(db=db)
    row = await uc.get_taxonomy_by_id(taxonomy_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    return SuccessResponse.ok(TaxonomyResponse.model_validate(row))


# ── Create / update / soft delete ───────────────────────────────────────

@router.post("", response_model=SuccessResponse[TaxonomyResponse], status_code=201)
async def create_taxonomy(
    payload: TaxonomyCreatePayload,
    db: DBSession,
    # NOTE: PermissionChecker enforces 'create'. Use case additionally enforces
    # 'manage_global' when payload.tenant_id is None.
    current_user: CurrentUser = Create,
):
    uc = SecurityTaxonomyUseCases(db=db)
    row = await uc.create_taxonomy(actor=current_user, payload=payload)
    await db.commit()
    return SuccessResponse.ok(TaxonomyResponse.model_validate(row))


@router.patch("/{taxonomy_id}", response_model=SuccessResponse[TaxonomyResponse])
async def update_taxonomy(
    taxonomy_id: str,
    updates: TaxonomyUpdatePayload,
    db: DBSession,
    current_user: CurrentUser = Update,
):
    uc = SecurityTaxonomyUseCases(db=db)
    row = await uc.update_taxonomy(
        actor=current_user, taxonomy_id=taxonomy_id, updates=updates,
    )
    await db.commit()
    return SuccessResponse.ok(TaxonomyResponse.model_validate(row))


@router.delete("/{taxonomy_id}", status_code=204)
async def soft_delete_taxonomy(
    taxonomy_id: str,
    body: _DeleteBody,
    db: DBSession,
    current_user: CurrentUser = Delete,
):
    uc = SecurityTaxonomyUseCases(db=db)
    await uc.soft_delete(
        actor=current_user, taxonomy_id=taxonomy_id, reason=body.reason,
    )
    await db.commit()


# ── Fork / refresh ──────────────────────────────────────────────────────

@router.post(
    "/{taxonomy_id}/fork",
    response_model=SuccessResponse[TaxonomyResponse], status_code=201,
)
async def fork_taxonomy(
    taxonomy_id: str,
    body: _ForkBody,
    db: DBSession,
    current_user: CurrentUser = Create,
):
    uc = SecurityTaxonomyUseCases(db=db)
    row = await uc.fork_to_tenant(
        actor=current_user, global_taxonomy_id=taxonomy_id,
        target_tenant_id=body.target_tenant_id,
    )
    await db.commit()
    return SuccessResponse.ok(TaxonomyResponse.model_validate(row))


@router.post(
    "/{taxonomy_id}/refresh-from-global",
    response_model=SuccessResponse[TaxonomyResponse],
)
async def refresh_taxonomy_from_global(
    taxonomy_id: str,
    db: DBSession,
    current_user: CurrentUser = Update,
):
    uc = SecurityTaxonomyUseCases(db=db)
    row = await uc.refresh_from_global(
        actor=current_user, taxonomy_id=taxonomy_id,
    )
    await db.commit()
    return SuccessResponse.ok(TaxonomyResponse.model_validate(row))


# ── Audit log ───────────────────────────────────────────────────────────

@router.get(
    "/{taxonomy_id}/audit-log",
    response_model=SuccessResponse[list[dict]],
)
async def list_audit_log(
    taxonomy_id: str,
    db: DBSession,
    change_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: CurrentUser = Audit,
):
    uc = SecurityTaxonomyUseCases(db=db)
    entries = await uc.list_audit_log(
        taxonomy_id=taxonomy_id, change_type=change_type, limit=limit,
    )
    return SuccessResponse.ok([
        {
            "id": e.id, "taxonomy_id": e.taxonomy_id,
            "changed_by": e.changed_by, "changed_at": e.changed_at.isoformat(),
            "change_type": e.change_type, "field_changes": e.field_changes,
            "reason": e.reason,
        }
        for e in entries
    ])


# ── Notifications ────────────────────────────────────────────────────────

@router.get(
    "/{taxonomy_id}/notifications",
    response_model=SuccessResponse[list[dict]],
)
async def list_notifications(
    taxonomy_id: str,
    db: DBSession,
    current_user: CurrentUser = Read,
):
    uc = SecurityTaxonomyUseCases(db=db)
    notifs = await uc.list_notifications(taxonomy_id)
    return SuccessResponse.ok([
        {
            "id": n.id,
            "taxonomy_id": n.taxonomy_id,
            "team_id": n.team_id,
            "notify_phase": n.notify_phase,
            "notify_channel": n.notify_channel,
            "escalation_minutes": n.escalation_minutes,
        }
        for n in notifs
    ])


@router.post(
    "/{taxonomy_id}/notifications",
    response_model=SuccessResponse[dict], status_code=201,
)
async def add_notification(
    taxonomy_id: str,
    payload: NotificationCreatePayload,
    db: DBSession,
    current_user: CurrentUser = Update,
):
    uc = SecurityTaxonomyUseCases(db=db)
    notif = await uc.add_notification(
        actor=current_user, taxonomy_id=taxonomy_id, payload=payload,
    )
    await db.commit()
    return SuccessResponse.ok({
        "id": notif.id, "taxonomy_id": notif.taxonomy_id,
        "team_id": notif.team_id, "notify_phase": notif.notify_phase,
        "notify_channel": notif.notify_channel,
        "escalation_minutes": notif.escalation_minutes,
    })


@router.delete(
    "/{taxonomy_id}/notifications/{notification_id}", status_code=204,
)
async def remove_notification(
    taxonomy_id: str,
    notification_id: str,
    db: DBSession,
    current_user: CurrentUser = Update,
):
    uc = SecurityTaxonomyUseCases(db=db)
    try:
        await uc.remove_notification(
            actor=current_user, notification_id=notification_id,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()


# ── Catalog mappings ─────────────────────────────────────────────────────

@router.get(
    "/{taxonomy_id}/catalog-mappings",
    response_model=SuccessResponse[list[dict]],
)
async def list_catalog_mappings(
    taxonomy_id: str,
    db: DBSession,
    current_user: CurrentUser = Read,
):
    uc = SecurityTaxonomyUseCases(db=db)
    mappings = await uc.list_catalog_mappings(taxonomy_id)
    return SuccessResponse.ok([
        {
            "id": m.id,
            "taxonomy_id": m.taxonomy_id,
            "service_catalog_item_id": m.service_catalog_item_id,
            "is_default": m.is_default,
            "priority_order": m.priority_order,
        }
        for m in mappings
    ])


@router.post(
    "/{taxonomy_id}/catalog-mappings",
    response_model=SuccessResponse[dict], status_code=201,
)
async def add_catalog_mapping(
    taxonomy_id: str,
    payload: CatalogMappingCreatePayload,
    db: DBSession,
    current_user: CurrentUser = Update,
):
    uc = SecurityTaxonomyUseCases(db=db)
    mapping = await uc.add_catalog_mapping(
        actor=current_user, taxonomy_id=taxonomy_id, payload=payload,
    )
    await db.commit()
    return SuccessResponse.ok({
        "id": mapping.id, "taxonomy_id": mapping.taxonomy_id,
        "service_catalog_item_id": mapping.service_catalog_item_id,
        "is_default": mapping.is_default,
        "priority_order": mapping.priority_order,
    })


@router.patch(
    "/{taxonomy_id}/catalog-mappings/{mapping_id}/set-default",
    response_model=SuccessResponse[dict],
)
async def set_default_catalog_mapping(
    taxonomy_id: str,
    mapping_id: str,
    db: DBSession,
    current_user: CurrentUser = Update,
):
    uc = SecurityTaxonomyUseCases(db=db)
    mapping = await uc.set_default_catalog_mapping(
        actor=current_user, mapping_id=mapping_id,
    )
    await db.commit()
    return SuccessResponse.ok({
        "id": mapping.id, "taxonomy_id": mapping.taxonomy_id,
        "is_default": mapping.is_default,
    })


@router.delete(
    "/{taxonomy_id}/catalog-mappings/{mapping_id}", status_code=204,
)
async def remove_catalog_mapping(
    taxonomy_id: str,
    mapping_id: str,
    db: DBSession,
    current_user: CurrentUser = Update,
):
    uc = SecurityTaxonomyUseCases(db=db)
    try:
        await uc.remove_catalog_mapping(
            actor=current_user, mapping_id=mapping_id,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Mapping not found")
    await db.commit()
