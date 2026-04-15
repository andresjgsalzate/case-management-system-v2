# backend/src/modules/email_config/router.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.email_config.application.smtp_use_cases import SmtpConfigUseCases
from backend.src.modules.email_config.application.template_use_cases import EmailTemplateUseCases

router = APIRouter(prefix="/api/v1/email-config", tags=["email_config"])
Manage = Depends(PermissionChecker("notifications", "create"))
Read   = Depends(PermissionChecker("notifications", "read"))


# ── DTOs ──────────────────────────────────────────────────────────────────────

class UpsertSmtpDTO(BaseModel):
    host: str
    port: int = 587
    username: str | None = None
    password: str | None = None
    from_email: str
    from_name: str = "CaseManager"
    use_tls: bool = True
    is_enabled: bool = False


class CreateTemplateDTO(BaseModel):
    name: str
    scope: str
    blocks: list = []


class UpdateTemplateDTO(BaseModel):
    name: str | None = None
    scope: str | None = None
    blocks: list | None = None
    is_active: bool | None = None


# ── SMTP endpoints ────────────────────────────────────────────────────────────

@router.get("/smtp", response_model=SuccessResponse[dict | None])
async def get_smtp_config(db: DBSession, _: CurrentUser = Read):
    uc = SmtpConfigUseCases(db)
    config = await uc.get()
    if not config:
        return SuccessResponse.ok(None)
    return SuccessResponse.ok({
        "id": config.id,
        "host": config.host,
        "port": config.port,
        "username": config.username,
        "from_email": config.from_email,
        "from_name": config.from_name,
        "use_tls": config.use_tls,
        "is_enabled": config.is_enabled,
        "updated_at": config.updated_at.isoformat(),
        # password intentionally omitted
    })


@router.put("/smtp", response_model=SuccessResponse[dict])
async def upsert_smtp_config(body: UpsertSmtpDTO, db: DBSession, _: CurrentUser = Manage):
    uc = SmtpConfigUseCases(db)
    config = await uc.upsert(
        host=body.host, port=body.port, username=body.username,
        password=body.password, from_email=body.from_email,
        from_name=body.from_name, use_tls=body.use_tls,
        is_enabled=body.is_enabled,
    )
    return SuccessResponse.ok({"id": config.id, "host": config.host, "is_enabled": config.is_enabled})


@router.post("/smtp/test", response_model=SuccessResponse[dict])
async def test_smtp_connection(db: DBSession, _: CurrentUser = Manage):
    uc = SmtpConfigUseCases(db)
    result = await uc.test_connection()
    return SuccessResponse.ok({"success": result["success"], "message": result["message"]})


# ── Template endpoints ────────────────────────────────────────────────────────

@router.get("/templates", response_model=SuccessResponse[list[dict]])
async def list_email_templates(db: DBSession, _: CurrentUser = Read):
    uc = EmailTemplateUseCases(db)
    templates = await uc.list_all()
    return SuccessResponse.ok([_serialize(t) for t in templates])


@router.post("/templates", status_code=201, response_model=SuccessResponse[dict])
async def create_email_template(body: CreateTemplateDTO, db: DBSession, _: CurrentUser = Manage):
    uc = EmailTemplateUseCases(db)
    tpl = await uc.create(name=body.name, scope=body.scope, blocks=body.blocks)
    return SuccessResponse.ok(_serialize(tpl))


@router.get("/templates/{template_id}", response_model=SuccessResponse[dict])
async def get_email_template(template_id: str, db: DBSession, _: CurrentUser = Read):
    uc = EmailTemplateUseCases(db)
    tpl = await uc.get(template_id)
    return SuccessResponse.ok(_serialize(tpl))


@router.put("/templates/{template_id}", response_model=SuccessResponse[dict])
async def update_email_template(
    template_id: str, body: UpdateTemplateDTO, db: DBSession, _: CurrentUser = Manage,
):
    uc = EmailTemplateUseCases(db)
    tpl = await uc.update(
        template_id=template_id,
        name=body.name, scope=body.scope,
        blocks=body.blocks, is_active=body.is_active,
    )
    return SuccessResponse.ok(_serialize(tpl))


@router.delete("/templates/{template_id}", status_code=204)
async def delete_email_template(template_id: str, db: DBSession, _: CurrentUser = Manage):
    uc = EmailTemplateUseCases(db)
    await uc.delete(template_id)


def _serialize(t) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "scope": t.scope,
        "blocks": t.blocks,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }
