from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.notes.application.use_cases import NoteUseCases

router = APIRouter(prefix="/api/v1/cases/{case_id}/notes", tags=["notes"])
NotesRead = Depends(PermissionChecker("notes", "read"))
NotesCreate = Depends(PermissionChecker("notes", "create"))


class NoteCreate(BaseModel):
    content: str


class NoteUpdate(BaseModel):
    content: str


@router.get("", response_model=SuccessResponse[list[dict]])
async def list_notes(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = NotesRead,
):
    uc = NoteUseCases(db=db)
    notes = await uc.list_for_case(case_id)
    return SuccessResponse.ok([
        {
            "id": n.id,
            "user_id": n.user_id,
            "content": n.content,
            "created_at": n.created_at.isoformat(),
        }
        for n in notes
    ])


@router.post("", status_code=201)
async def create_note(
    case_id: str,
    body: NoteCreate,
    db: DBSession,
    current_user: CurrentUser = NotesCreate,
):
    uc = NoteUseCases(db=db)
    note = await uc.create(
        case_id=case_id,
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        content=body.content,
    )
    return SuccessResponse.ok({"id": note.id})


@router.patch("/{note_id}", response_model=SuccessResponse[dict])
async def update_note(
    case_id: str,
    note_id: str,
    body: NoteUpdate,
    db: DBSession,
    current_user: CurrentUser = NotesCreate,
):
    uc = NoteUseCases(db=db)
    note = await uc.update(note_id=note_id, user_id=current_user.user_id, content=body.content)
    return SuccessResponse.ok({"id": note.id, "content": note.content})


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    case_id: str,
    note_id: str,
    db: DBSession,
    current_user: CurrentUser = NotesCreate,
):
    uc = NoteUseCases(db=db)
    await uc.delete(note_id=note_id, user_id=current_user.user_id)
