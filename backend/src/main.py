from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.src.core.config import get_settings
from backend.src.core.database import engine
from backend.src.core.events.registry import register_all_handlers
from backend.src.core.exceptions import AppError
from backend.src.core.redis_client import close_redis, init_redis
from backend.src.modules.health.router import router as health_router
from backend.src.modules.roles.router import router as roles_router
from backend.src.modules.auth.router import router as auth_router
from backend.src.modules.users.router import router as users_router
from backend.src.modules.teams.router import router as teams_router
from backend.src.modules.case_statuses.router import router as case_statuses_router
from backend.src.modules.case_priorities.router import router as case_priorities_router
from backend.src.modules.cases.router import router as cases_router
from backend.src.modules.activity.router import router as activity_router
from backend.src.modules.applications.router import router as applications_router
from backend.src.modules.origins.router import router as origins_router
from backend.src.modules.classification.router import router as classification_router
from backend.src.modules.sla.router import router as sla_router
from backend.src.modules.chat.router import router as chat_router
from backend.src.modules.notes.router import router as notes_router
from backend.src.modules.attachments.router import router as attachments_router
from backend.src.modules.todos.router import router as todos_router
from backend.src.modules.time_entries.router import router as time_entries_router
from backend.src.modules.dispositions.router import router as dispositions_router
from backend.src.modules.metrics.router import router as metrics_router
from backend.src.modules.search.router import router as search_router
from backend.src.modules.knowledge_base.router import router as kb_router
from backend.src.modules.notifications.router import router as notifications_router
from backend.src.modules.audit.router import router as audit_router
from backend.src.modules.automation.router import router as automation_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_redis()
    register_all_handlers()
    settings = get_settings()
    from backend.src.modules.sla.application.jobs import start_sla_scheduler
    start_sla_scheduler(interval_minutes=settings.SLA_CHECK_INTERVAL_MINUTES)
    yield
    # Shutdown
    from backend.src.modules.sla.application.jobs import stop_sla_scheduler
    stop_sla_scheduler()
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Case Management System API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        from backend.src.core.exceptions import (
            ConflictError,
            ForbiddenError,
            NotFoundError,
            UnauthorizedError,
            PermissionDeniedError,
            BusinessRuleError,
            ValidationError,
        )
        status_map = {
            NotFoundError: 404,
            ConflictError: 409,
            ForbiddenError: 403,
            UnauthorizedError: 401,
            PermissionDeniedError: 403,
            BusinessRuleError: 422,
            ValidationError: 400,
        }
        status_code = status_map.get(type(exc), 400)
        return JSONResponse(
            status_code=status_code,
            content={"success": False, "error": exc.code, "message": exc.message},
        )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(roles_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(teams_router, prefix="/api/v1")
    app.include_router(case_statuses_router)
    app.include_router(case_priorities_router)
    app.include_router(cases_router)
    app.include_router(activity_router)
    app.include_router(applications_router)
    app.include_router(origins_router)
    app.include_router(classification_router)
    app.include_router(sla_router)
    app.include_router(chat_router)
    app.include_router(notes_router)
    app.include_router(attachments_router)
    app.include_router(todos_router)
    app.include_router(time_entries_router)
    app.include_router(dispositions_router)
    app.include_router(metrics_router)
    app.include_router(search_router)
    app.include_router(kb_router)
    app.include_router(notifications_router)
    app.include_router(audit_router)
    app.include_router(automation_router)

    return app


app = create_app()
