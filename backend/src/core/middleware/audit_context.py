import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class AuditContextMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that generates one correlation_id per HTTP request
    and injects it (along with User-Agent and request path) into the audit
    ContextVars before any handler runs.

    The actor_id is set later by the PermissionChecker dependency after JWT
    verification — it calls set_current_actor() which only updates _current_actor
    without overwriting the correlation_id already set here.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        from backend.src.modules.audit.application.middleware import set_audit_context

        correlation_id = str(uuid.uuid4())
        user_agent = (request.headers.get("user-agent") or "")[:500]
        request_path = f"{request.method} {request.url.path}"[:200]

        set_audit_context(
            actor_id=None,
            correlation_id=correlation_id,
            user_agent=user_agent,
            request_path=request_path,
        )

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response
