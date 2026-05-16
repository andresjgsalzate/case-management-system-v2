"""HTTP router for the prioritization module (Sub-spec 03)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select

from backend.src.core.dependencies import DBSession
from backend.src.core.middleware.permission_checker import (
    CurrentUser,
    PermissionChecker,
)
from backend.src.core.responses import SuccessResponse
from backend.src.modules.prioritization.application.dtos import (
    CalculationResponse,
    CreateFormulaVersionPayload,
    CriterionResponse,
    FormulaResponse,
    ScaleResponse,
)
from backend.src.modules.prioritization.application.use_cases import (
    PrioritizationUseCases,
)
from backend.src.modules.prioritization.infrastructure.models import (
    PrioritizationCriterionModel,
    PrioritizationFormulaModel,
    PrioritizationScaleModel,
)

router = APIRouter(prefix="/api/v1/prioritization", tags=["prioritization"])

Read = Depends(PermissionChecker("prioritization", "read"))
ManageFormulas = Depends(PermissionChecker("prioritization", "manage_formulas"))
ReadCalcs = Depends(PermissionChecker("prioritization", "read_calculations"))
Recalculate = Depends(PermissionChecker("prioritization", "recalculate"))


# ── Criteria (read-only in Phase 1; admin uses seed) ────────────────────

@router.get("/criteria", response_model=SuccessResponse[list[CriterionResponse]])
async def list_criteria(
    db: DBSession,
    current_user: CurrentUser = Read,
):
    """Globals + own-tenant criteria."""
    stmt = (
        select(PrioritizationCriterionModel)
        .where(
            or_(
                PrioritizationCriterionModel.tenant_id == current_user.tenant_id,
                PrioritizationCriterionModel.tenant_id.is_(None),
            ),
            PrioritizationCriterionModel.is_active.is_(True),
        )
        .order_by(PrioritizationCriterionModel.sort_order)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return SuccessResponse.ok([CriterionResponse.model_validate(r) for r in rows])


@router.get(
    "/criteria/{criterion_id}/scales",
    response_model=SuccessResponse[list[ScaleResponse]],
)
async def list_scales(
    criterion_id: str,
    db: DBSession,
    current_user: CurrentUser = Read,
):
    stmt = (
        select(PrioritizationScaleModel)
        .where(PrioritizationScaleModel.criterion_id == criterion_id)
        .order_by(PrioritizationScaleModel.sort_order)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return SuccessResponse.ok([ScaleResponse.model_validate(r) for r in rows])


# ── Formulas ────────────────────────────────────────────────────────────

@router.get("/formulas", response_model=SuccessResponse[list[FormulaResponse]])
async def list_formulas(
    db: DBSession,
    logical_key: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    current_user: CurrentUser = Read,
):
    stmt = select(PrioritizationFormulaModel).where(
        or_(
            PrioritizationFormulaModel.tenant_id == current_user.tenant_id,
            PrioritizationFormulaModel.tenant_id.is_(None),
        )
    )
    if logical_key:
        stmt = stmt.where(PrioritizationFormulaModel.logical_key == logical_key)
    if active_only:
        stmt = stmt.where(PrioritizationFormulaModel.is_active.is_(True))
    stmt = stmt.order_by(
        PrioritizationFormulaModel.logical_key,
        PrioritizationFormulaModel.version.desc(),
    )
    rows = (await db.execute(stmt)).scalars().all()
    return SuccessResponse.ok([FormulaResponse.model_validate(r) for r in rows])


@router.get(
    "/formulas/by-key/{logical_key}/active",
    response_model=SuccessResponse[FormulaResponse],
)
async def get_active_formula_by_key(
    logical_key: str,
    db: DBSession,
    current_user: CurrentUser = Read,
):
    """Active formula for tenant; falls back to global if no tenant override."""
    uc = PrioritizationUseCases(db=db)
    formula = await uc._get_active_formula(logical_key, current_user.tenant_id)
    if not formula:
        # Fallback to global
        formula = await uc._get_active_formula(logical_key, None)
    if not formula:
        raise HTTPException(
            status_code=404,
            detail=f"No active formula found for logical_key '{logical_key}'",
        )
    return SuccessResponse.ok(FormulaResponse.model_validate(formula))


@router.get("/formulas/{formula_id}", response_model=SuccessResponse[FormulaResponse])
async def get_formula(
    formula_id: str,
    db: DBSession,
    current_user: CurrentUser = Read,
):
    row = await db.get(PrioritizationFormulaModel, formula_id)
    if not row:
        raise HTTPException(status_code=404, detail="Formula not found")
    return SuccessResponse.ok(FormulaResponse.model_validate(row))


@router.post(
    "/formulas",
    response_model=SuccessResponse[FormulaResponse],
    status_code=201,
)
async def create_formula_version(
    payload: CreateFormulaVersionPayload,
    db: DBSession,
    # NOTE: PermissionChecker enforces 'manage_formulas'. Use case upgrades to
    # 'manage_global' when payload.tenant_id is None.
    current_user: CurrentUser = ManageFormulas,
):
    uc = PrioritizationUseCases(db=db)
    formula = await uc.create_formula_version(
        actor=current_user,
        tenant_id=payload.tenant_id,
        logical_key=payload.logical_key,
        base_version_id=payload.base_version_id,
        name=payload.name,
        description=payload.description,
        criteria_weights={c.code: c.weight for c in payload.criteria_weights},
        thresholds=[
            (t.min_value, t.max_value, t.priority_name)
            for t in payload.thresholds
        ],
    )
    await db.commit()
    return SuccessResponse.ok(FormulaResponse.model_validate(formula))


# ── Case-scoped operations ──────────────────────────────────────────────

# These endpoints live under /api/v1/cases/{case_id}/... — register a separate
# APIRouter and mount with empty prefix so they sit on the cases path.
case_router = APIRouter(prefix="/api/v1/cases", tags=["prioritization"])


@case_router.get(
    "/{case_id}/priority-calculations",
    response_model=SuccessResponse[list[CalculationResponse]],
)
async def list_case_priority_calculations(
    case_id: str,
    db: DBSession,
    limit: int = Query(default=50, ge=1, le=500),
    current_user: CurrentUser = ReadCalcs,
):
    uc = PrioritizationUseCases(db=db)
    rows = await uc.list_calculations(case_id=case_id, limit=limit)
    return SuccessResponse.ok([CalculationResponse.model_validate(r) for r in rows])


@case_router.post(
    "/{case_id}/recalculate-priority",
    response_model=SuccessResponse[CalculationResponse],
)
async def recalculate_priority(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = Recalculate,
):
    uc = PrioritizationUseCases(db=db)
    calc = await uc.manual_recalculation(actor=current_user, case_id=case_id)
    await db.commit()
    return SuccessResponse.ok(CalculationResponse.model_validate(calc))


@case_router.post(
    "/{case_id}/promote-to-formula-version",
    response_model=SuccessResponse[CalculationResponse],
)
async def promote_to_formula_version(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = Recalculate,
):
    uc = PrioritizationUseCases(db=db)
    calc = await uc.promote_case_to_new_formula_version(
        actor=current_user, case_id=case_id,
    )
    await db.commit()
    return SuccessResponse.ok(CalculationResponse.model_validate(calc))
