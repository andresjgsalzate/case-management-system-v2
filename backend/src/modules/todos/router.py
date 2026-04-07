from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.todos.application.use_cases import TodoUseCases

router = APIRouter(prefix="/api/v1/cases/{case_id}/todos", tags=["todos"])
TodoRead = Depends(PermissionChecker("todos", "read"))
TodoCreate = Depends(PermissionChecker("todos", "create"))


class TodoCreateDTO(BaseModel):
    title: str
    description: str | None = None
    assigned_to_id: str | None = None
    due_date: datetime | None = None


@router.get("", response_model=SuccessResponse[list[dict]])
async def list_todos(
    case_id: str,
    db: DBSession,
    include_archived: bool = False,
    current_user: CurrentUser = TodoRead,
):
    uc = TodoUseCases(db=db)
    todos = await uc.list_for_case(case_id, include_archived=include_archived)
    return SuccessResponse.ok([
        {
            "id": t.id,
            "title": t.title,
            "is_completed": t.is_completed,
            "is_archived": t.is_archived,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in todos
    ])


@router.post("", status_code=201)
async def create_todo(
    case_id: str,
    body: TodoCreateDTO,
    db: DBSession,
    current_user: CurrentUser = TodoCreate,
):
    uc = TodoUseCases(db=db)
    todo = await uc.create(
        case_id=case_id,
        created_by_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        **body.model_dump(),
    )
    return SuccessResponse.ok({"id": todo.id, "title": todo.title})


@router.post("/{todo_id}/complete")
async def complete_todo(
    case_id: str,
    todo_id: str,
    db: DBSession,
    current_user: CurrentUser = TodoCreate,
):
    uc = TodoUseCases(db=db)
    todo = await uc.complete(todo_id=todo_id, user_id=current_user.user_id)
    return SuccessResponse.ok({"id": todo.id, "is_completed": todo.is_completed})


@router.post("/{todo_id}/archive", status_code=204)
async def archive_todo(
    case_id: str,
    todo_id: str,
    db: DBSession,
    current_user: CurrentUser = TodoCreate,
):
    uc = TodoUseCases(db=db)
    await uc.archive(todo_id=todo_id)
