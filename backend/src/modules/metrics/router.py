from fastapi import APIRouter, Depends, Query

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.metrics.application.use_cases import MetricsUseCases

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])
MetricsRead = Depends(PermissionChecker("metrics", "read"))


@router.get("/dashboard")
async def get_dashboard(
    db: DBSession,
    current_user: CurrentUser = MetricsRead,
):
    uc = MetricsUseCases(db=db)
    return SuccessResponse.ok(await uc.get_dashboard_summary())


@router.get("/cases/by-status")
async def cases_by_status(
    db: DBSession,
    current_user: CurrentUser = MetricsRead,
):
    uc = MetricsUseCases(db=db)
    return SuccessResponse.ok(await uc.get_cases_by_status())


@router.get("/cases/by-priority")
async def cases_by_priority(
    db: DBSession,
    current_user: CurrentUser = MetricsRead,
):
    uc = MetricsUseCases(db=db)
    return SuccessResponse.ok(await uc.get_cases_by_priority())


@router.get("/cases/by-agent")
async def cases_by_agent(
    db: DBSession,
    limit: int = Query(default=10, le=50),
    current_user: CurrentUser = MetricsRead,
):
    uc = MetricsUseCases(db=db)
    return SuccessResponse.ok(await uc.get_cases_by_agent(limit=limit))


@router.get("/cases/by-application")
async def cases_by_application(
    db: DBSession,
    current_user: CurrentUser = MetricsRead,
):
    uc = MetricsUseCases(db=db)
    return SuccessResponse.ok(await uc.get_cases_by_application())


@router.get("/cases/trend")
async def cases_trend(
    db: DBSession,
    days: int = Query(default=30, le=90),
    current_user: CurrentUser = MetricsRead,
):
    uc = MetricsUseCases(db=db)
    return SuccessResponse.ok(await uc.get_cases_created_by_day(days=days))


@router.get("/sla/compliance")
async def sla_compliance(
    db: DBSession,
    current_user: CurrentUser = MetricsRead,
):
    uc = MetricsUseCases(db=db)
    return SuccessResponse.ok(await uc.get_sla_compliance_rate())


@router.get("/resolution-time")
async def resolution_time(
    db: DBSession,
    current_user: CurrentUser = MetricsRead,
):
    uc = MetricsUseCases(db=db)
    return SuccessResponse.ok(await uc.get_avg_resolution_minutes())
