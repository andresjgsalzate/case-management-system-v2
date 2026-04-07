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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_redis()
    register_all_handlers()
    yield
    # Shutdown
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
            ConflictError, ForbiddenError, NotFoundError, UnauthorizedError, PermissionDeniedError,
        )
        status_map = {
            NotFoundError: 404,
            ConflictError: 409,
            ForbiddenError: 403,
            UnauthorizedError: 401,
            PermissionDeniedError: 403,
        }
        status_code = status_map.get(type(exc), 400)
        return JSONResponse(
            status_code=status_code,
            content={"success": False, "error": exc.code, "message": exc.message},
        )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(roles_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")

    return app


app = create_app()
