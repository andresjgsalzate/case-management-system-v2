from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse

from backend.src.core.dependencies import DBSession
from backend.src.core.config import get_settings
from backend.src.modules.attachments.application.use_cases import AttachmentUseCases
from backend.src.modules.attachments.infrastructure.models import CaseAttachmentModel
from backend.src.core.exceptions import NotFoundError
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(prefix="/api/v1/cases/{case_id}/attachments", tags=["attachments"])
AttachRead = Depends(PermissionChecker("attachments", "read"))
AttachCreate = Depends(PermissionChecker("attachments", "create"))


@router.get("", response_model=SuccessResponse[list[dict]])
async def list_attachments(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = AttachRead,
):
    uc = AttachmentUseCases(db=db, upload_dir=get_settings().UPLOAD_DIR)
    attachments = await uc.list_for_case(case_id)
    return SuccessResponse.ok([
        {
            "id": a.id,
            "original_filename": a.original_filename,
            "mime_type": a.mime_type,
            "file_size": a.file_size,
            "created_at": a.created_at.isoformat(),
        }
        for a in attachments
    ])


@router.post("", status_code=201)
async def upload_attachment(
    case_id: str,
    db: DBSession,
    file: UploadFile = File(...),
    current_user: CurrentUser = AttachCreate,
):
    uc = AttachmentUseCases(db=db, upload_dir=get_settings().UPLOAD_DIR)
    att = await uc.upload(
        case_id=case_id,
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        file=file,
    )
    return SuccessResponse.ok({"id": att.id, "original_filename": att.original_filename})


@router.get("/{attachment_id}/download")
async def download_attachment(
    case_id: str,
    attachment_id: str,
    db: DBSession,
    current_user: CurrentUser = AttachRead,
):
    """Descarga autenticada — el JWT valida el acceso antes de servir el archivo."""
    att = await db.get(CaseAttachmentModel, attachment_id)
    if not att or att.case_id != case_id or att.is_deleted:
        raise NotFoundError(f"Adjunto {attachment_id} no encontrado")
    file_path = Path(att.file_path)
    if not file_path.exists():
        raise NotFoundError("Archivo no encontrado en disco")
    return FileResponse(
        path=str(file_path),
        filename=att.original_filename,
        media_type=att.mime_type,
    )


@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(
    case_id: str,
    attachment_id: str,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("attachments", "delete")),
):
    uc = AttachmentUseCases(db=db, upload_dir=get_settings().UPLOAD_DIR)
    await uc.delete(attachment_id=attachment_id, user_id=current_user.user_id)
