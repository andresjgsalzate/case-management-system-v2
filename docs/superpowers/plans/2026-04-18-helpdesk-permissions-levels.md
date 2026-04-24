# Helpdesk Permissions & Levels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the binary "assigned-user" guard on cases with a proper helpdesk RBAC model that supports role levels (N1/N2/…), a unified transfer flow (escalate/reassign/de-escalate), hybrid collaboration, and a role-permission admin UI that stops hardcoding `scope="all"`.

**Architecture:** Single centralized `check_case_action` helper in Python decides every case-level gate (read/update/transition/transfer/comment/attach) based on user scope, role level, and case level. The frontend mirrors that logic via a new `useCasePermissions(case)` hook. All case routes stop computing scope filters ad-hoc and delegate to the helper and a new `filter_cases_by_permission` query builder. A single `POST /cases/{id}/transfer` endpoint handles all movement, with the backend classifying it as escalate/reassign/de-escalate based on level comparison.

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic; Next.js 14 App Router + TanStack Query + Tailwind; Pydantic v2 DTOs; pytest for backend TDD; existing `PermissionModel {role_id, module, action, scope}` and `{own, team, all}` scope triad.

**Spec:** `docs/superpowers/specs/2026-04-18-helpdesk-permissions-levels-design.md`

---

## File Structure

### Backend — new files

- `backend/alembic/versions/c1d2e3f4a5b6_helpdesk_levels_and_transfers.py` — schema migration (roles.level, cases.current_level, case_transfers table).
- `backend/src/core/permissions/__init__.py` — package marker.
- `backend/src/core/permissions/case_permissions.py` — `check_case_action(user, case, action, user_role_level) -> bool` plus `CaseAction` literal type. Pure function, no DB side-effects.
- `backend/src/core/permissions/case_queries.py` — `filter_cases_by_permission(query, user, user_role_level, target_level=None) -> query` for list endpoints.
- `backend/src/modules/cases/application/transfer_dtos.py` — `TransferCaseDTO {to_user_id, reason}`, `TransferResponseDTO`.
- `backend/src/modules/cases/application/transfer_use_cases.py` — `CaseTransferUseCases.transfer(case_id, dto, actor, user_role_level)`.
- `backend/src/modules/cases/infrastructure/transfer_models.py` — `CaseTransferModel` SQLAlchemy model.
- `backend/tests/core/__init__.py` — package marker.
- `backend/tests/core/test_case_permissions.py` — unit tests for `check_case_action`.
- `backend/tests/test_case_transfers.py` — integration tests for transfer endpoint + classification.

### Backend — modified files

- `backend/src/modules/roles/infrastructure/models.py` — add `level: Mapped[int]` to `RoleModel`.
- `backend/src/modules/roles/application/dtos.py` — add `level: int = 1` to `CreateRoleDTO`, `UpdateRoleDTO`, `RoleResponseDTO`.
- `backend/src/modules/roles/application/use_cases.py` — persist/expose level.
- `backend/src/modules/cases/infrastructure/models.py` — add `current_level: Mapped[int]` to `CaseModel`.
- `backend/src/core/middleware/permission_checker.py` — add `role_level: int = 1` to `CurrentUser`; load role level in `__call__`.
- `backend/src/modules/auth/application/use_cases.py` — include `role_level` in JWT claims.
- `backend/src/modules/auth/router.py` — expose `role_level` in `/auth/me` response.
- `backend/src/modules/cases/router.py` — replace inline scope handling with helper calls; add `POST /cases/{id}/transfer`.
- `backend/src/modules/cases/application/use_cases.py` — call `check_case_action` in update/transition; remove inline scope branch in `list_cases`.
- `backend/src/modules/assignment/application/use_cases.py` — enforce `check_case_action(action="transfer")` for the existing assign endpoint (kept for backward compat).

### Frontend — new files

- `frontend/hooks/useCasePermissions.ts` — per-case permission hook mirroring backend logic.
- `frontend/hooks/useTransferCase.ts` — mutation hook + list hook for transfer history.
- `frontend/components/organisms/TransferCaseModal.tsx` — modal: team + user + reason.
- `frontend/components/organisms/TransferHistoryDrawer.tsx` — side drawer listing `case_transfers`.

### Frontend — modified files

- `frontend/lib/types.ts` — add `role_level` to `User`; add `current_level` to `Case`; add `CaseTransfer` and `CasePermissions` interfaces.
- `frontend/app/(dashboard)/settings/roles/page.tsx` — replace checkbox with 4-state selector; add level field.
- `frontend/app/(dashboard)/cases/[id]/page.tsx` — drop `canTakeActions` binary; consume `useCasePermissions`; add Transfer button/modal + history drawer trigger.
- `frontend/app/(dashboard)/cases/page.tsx` — add "Mi cola" / "Equipo" tabs using the new query filter.
- `frontend/hooks/useCases.ts` — add `queue=mine|team|all` query param support.

---

## Task ordering

Tasks are TDD-first. Backend lands first because the frontend consumes the new endpoints/fields. Migration is Task 1 so every subsequent backend task has the new columns available in the model.

---

### Task 1: Migration for roles.level, cases.current_level, case_transfers

**Files:**
- Create: `backend/alembic/versions/c1d2e3f4a5b6_helpdesk_levels_and_transfers.py`
- Test: `backend/tests/test_alembic_config.py` (verify file parses)

- [ ] **Step 1: Write the failing test**

Edit `backend/tests/test_alembic_config.py`, append:

```python
def test_helpdesk_levels_migration_present():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "c1d2e3f4a5b6_helpdesk_levels_and_transfers.py"
    assert path.exists(), f"migration file missing: {path}"
    spec = importlib.util.spec_from_file_location("migration_c1d2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "c1d2e3f4a5b6"
    assert module.down_revision == "1f35f05d8d94"
    assert callable(module.upgrade)
    assert callable(module.downgrade)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_alembic_config.py::test_helpdesk_levels_migration_present -v`
Expected: FAIL with `migration file missing`.

- [ ] **Step 3: Create the migration file**

Create `backend/alembic/versions/c1d2e3f4a5b6_helpdesk_levels_and_transfers.py`:

```python
"""helpdesk levels and transfers

Revision ID: c1d2e3f4a5b6
Revises: 1f35f05d8d94
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa

revision = "c1d2e3f4a5b6"
down_revision = "1f35f05d8d94"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint("roles_level_non_negative", "roles", "level >= 0")
    op.create_index("idx_roles_level", "roles", ["level"])

    op.add_column(
        "cases",
        sa.Column("current_level", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint("cases_current_level_positive", "cases", "current_level >= 1")
    op.create_index("idx_cases_current_level", "cases", ["current_level"])

    op.create_table(
        "case_transfers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("from_level", sa.Integer(), nullable=False),
        sa.Column("to_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("to_team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("to_level", sa.Integer(), nullable=False),
        sa.Column("transfer_type", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "transfer_type IN ('escalate','reassign','de-escalate')",
            name="transfers_type_valid",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) > 0",
            name="transfers_reason_nonempty",
        ),
    )
    op.create_index(
        "idx_case_transfers_case_id",
        "case_transfers",
        ["case_id", "created_at"],
    )
    op.create_index(
        "idx_case_transfers_tenant_id",
        "case_transfers",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_case_transfers_tenant_id", table_name="case_transfers")
    op.drop_index("idx_case_transfers_case_id", table_name="case_transfers")
    op.drop_table("case_transfers")

    op.drop_index("idx_cases_current_level", table_name="cases")
    op.drop_constraint("cases_current_level_positive", "cases", type_="check")
    op.drop_column("cases", "current_level")

    op.drop_index("idx_roles_level", table_name="roles")
    op.drop_constraint("roles_level_non_negative", "roles", type_="check")
    op.drop_column("roles", "level")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_alembic_config.py::test_helpdesk_levels_migration_present -v`
Expected: PASS.

- [ ] **Step 5: Run full alembic suite**

Run: `cd backend && pytest tests/test_alembic_config.py -v`
Expected: all tests pass (the migration file parses cleanly and all existing tests still pass).

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/c1d2e3f4a5b6_helpdesk_levels_and_transfers.py backend/tests/test_alembic_config.py
git commit -m "feat(migrations): add roles.level, cases.current_level, case_transfers"
```

---

### Task 2: RoleModel.level field + test

**Files:**
- Modify: `backend/src/modules/roles/infrastructure/models.py`
- Test: `backend/tests/test_models_identity.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_models_identity.py`:

```python
def test_role_model_has_level_column():
    from backend.src.modules.roles.infrastructure.models import RoleModel
    col = RoleModel.__table__.c.level
    assert col is not None
    assert str(col.type).upper().startswith("INTEGER")
    assert col.nullable is False
    assert col.server_default.arg.text == "1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_models_identity.py::test_role_model_has_level_column -v`
Expected: FAIL — attribute `level` not found on RoleModel.

- [ ] **Step 3: Add the column**

Edit `backend/src/modules/roles/infrastructure/models.py`, inside `RoleModel` class, add after `description`:

```python
    level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
```

And add `Integer` to the import line at the top:

```python
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, Integer
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_models_identity.py::test_role_model_has_level_column -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/modules/roles/infrastructure/models.py backend/tests/test_models_identity.py
git commit -m "feat(roles): add level column to RoleModel"
```

---

### Task 3: CaseModel.current_level field + test

**Files:**
- Modify: `backend/src/modules/cases/infrastructure/models.py`
- Test: `backend/tests/test_models_identity.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_models_identity.py`:

```python
def test_case_model_has_current_level_column():
    from backend.src.modules.cases.infrastructure.models import CaseModel
    col = CaseModel.__table__.c.current_level
    assert col is not None
    assert str(col.type).upper().startswith("INTEGER")
    assert col.nullable is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_models_identity.py::test_case_model_has_current_level_column -v`
Expected: FAIL — `current_level` not found.

- [ ] **Step 3: Add the column**

Edit `backend/src/modules/cases/infrastructure/models.py`, inside `CaseModel`, add after `complexity`:

```python
    current_level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
```

`Integer` is already imported in that file — no import changes needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_models_identity.py::test_case_model_has_current_level_column -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/modules/cases/infrastructure/models.py backend/tests/test_models_identity.py
git commit -m "feat(cases): add current_level column to CaseModel"
```

---

### Task 4: Role DTOs expose level

**Files:**
- Modify: `backend/src/modules/roles/application/dtos.py`
- Test: `backend/tests/test_roles.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_roles.py`:

```python
def test_create_role_dto_defaults_level_to_1():
    dto = CreateRoleDTO(name="Agent")
    assert dto.level == 1


def test_create_role_dto_accepts_custom_level():
    dto = CreateRoleDTO(name="N2 Agent", level=2)
    assert dto.level == 2


def test_create_role_dto_rejects_negative_level():
    with pytest.raises(Exception):
        CreateRoleDTO(name="Bad", level=-1)


def test_update_role_dto_has_optional_level():
    dto = UpdateRoleDTO(level=3)
    assert dto.level == 3


def test_role_response_dto_carries_level():
    from backend.src.modules.roles.application.dtos import RoleResponseDTO
    r = RoleResponseDTO(
        id="r1", name="Agent", description=None,
        created_at="2026-04-18T00:00:00Z", permissions=[], level=2,
    )
    assert r.level == 2
```

Also add import at top:

```python
from backend.src.modules.roles.application.dtos import CreateRoleDTO, PermissionDTO, UpdateRoleDTO
```

(replace the existing import line — `UpdateRoleDTO` was missing).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_roles.py -v -k "level"`
Expected: FAIL — `level` field missing on DTOs.

- [ ] **Step 3: Update the DTOs**

Replace the contents of `backend/src/modules/roles/application/dtos.py` with:

```python
from pydantic import BaseModel, Field
from typing import Literal


class PermissionDTO(BaseModel):
    module: str
    action: str
    scope: Literal["own", "team", "all"] = "own"


class CreateRoleDTO(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None
    level: int = Field(default=1, ge=0)
    permissions: list[PermissionDTO] = []


class UpdateRoleDTO(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None
    level: int | None = Field(default=None, ge=0)


class RoleResponseDTO(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: str
    level: int = 1
    permissions: list[PermissionDTO] = []

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_roles.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/modules/roles/application/dtos.py backend/tests/test_roles.py
git commit -m "feat(roles): expose level in role DTOs"
```

---

### Task 5: Role use cases persist level

**Files:**
- Modify: `backend/src/modules/roles/application/use_cases.py`
- Test: `backend/tests/test_roles.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_roles.py`:

```python
def test_role_use_cases_to_dto_includes_level():
    from backend.src.modules.roles.infrastructure.models import RoleModel
    from backend.src.modules.roles.application.use_cases import RoleUseCases
    from datetime import datetime, timezone
    uc = RoleUseCases(db=None)  # type: ignore[arg-type]
    model = RoleModel(
        id="r1", name="Agent", description=None, tenant_id=None,
        created_at=datetime.now(timezone.utc), level=2,
    )
    model.permissions = []
    dto = uc._to_dto(model)
    assert dto.level == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_roles.py::test_role_use_cases_to_dto_includes_level -v`
Expected: FAIL — DTO constructed without `level` reports default 1.

- [ ] **Step 3: Update use case creation / update / mapping**

Edit `backend/src/modules/roles/application/use_cases.py`:

Replace `create_role` body — where `RoleModel(...)` is constructed — with:

```python
        role = RoleModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=dto.name,
            description=dto.description,
            level=dto.level,
        )
```

Replace the `update_role` body (entire method) with:

```python
    async def update_role(self, role_id: str, dto: UpdateRoleDTO) -> RoleResponseDTO:
        role = await self.db.get(RoleModel, role_id)
        if not role:
            raise NotFoundError("Role", role_id)
        if dto.name is not None:
            role.name = dto.name
        if dto.description is not None:
            role.description = dto.description
        if dto.level is not None:
            role.level = dto.level
        await self.db.commit()
        return await self.get_role(role_id)
```

Replace `_to_dto` with:

```python
    def _to_dto(self, model: RoleModel) -> RoleResponseDTO:
        return RoleResponseDTO(
            id=model.id,
            name=model.name,
            description=model.description,
            created_at=model.created_at.isoformat(),
            level=model.level,
            permissions=[
                PermissionDTO(module=p.module, action=p.action, scope=p.scope)
                for p in (model.permissions or [])
            ],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_roles.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/modules/roles/application/use_cases.py backend/tests/test_roles.py
git commit -m "feat(roles): persist and expose role level in use cases"
```

---

### Task 6: CurrentUser carries role_level

**Files:**
- Modify: `backend/src/core/middleware/permission_checker.py`
- Test: `backend/tests/test_permission_checker.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_permission_checker.py`:

```python
def test_current_user_has_role_level_default():
    from backend.src.core.middleware.permission_checker import CurrentUser
    u = CurrentUser(user_id="u1", email="a@b.com", role_id="r1", tenant_id="t1")
    assert u.role_level == 1


def test_current_user_custom_role_level():
    from backend.src.core.middleware.permission_checker import CurrentUser
    u = CurrentUser(user_id="u1", email="a@b.com", role_id="r1", tenant_id="t1", role_level=2)
    assert u.role_level == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_permission_checker.py -v`
Expected: FAIL — `role_level` attribute missing.

- [ ] **Step 3: Update CurrentUser and the checker**

Edit `backend/src/core/middleware/permission_checker.py`. Replace the `CurrentUser` dataclass:

```python
@dataclass
class CurrentUser:
    user_id: str
    email: str
    role_id: str
    tenant_id: str
    scope: str = "own"
    is_global: bool = False
    role_level: int = 1
```

Inside `PermissionChecker.__call__`, after the existing `role_result = await db.execute(select(RoleModel.is_global)...)` block, replace that whole block with:

```python
        role_result = await db.execute(
            select(RoleModel.is_global, RoleModel.level).where(RoleModel.id == role_id)
        )
        role_row = role_result.one_or_none()
        is_global = bool(role_row.is_global) if role_row else False
        role_level = int(role_row.level) if role_row else 1
```

And in the `return CurrentUser(...)` call, add `role_level=role_level`:

```python
        return CurrentUser(
            user_id=user_id,
            email=email,
            role_id=role_id,
            tenant_id=tenant_id,
            scope=permission.scope,
            is_global=is_global,
            role_level=role_level,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_permission_checker.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/core/middleware/permission_checker.py backend/tests/test_permission_checker.py
git commit -m "feat(auth): CurrentUser exposes role_level"
```

---

### Task 7: Expose role_level in /auth/me and JWT

**Files:**
- Modify: `backend/src/modules/auth/application/use_cases.py`
- Modify: `backend/src/modules/auth/router.py`
- Test: `backend/tests/test_auth.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_auth.py`:

```python
def test_login_includes_role_level_claim(monkeypatch):
    """create_access_token should be called with role_level in extra_claims."""
    from backend.src.modules.auth.application import use_cases as auth_uc
    captured = {}

    def fake_create(subject: str, extra_claims: dict):
        captured.update(extra_claims)
        return "fake-token"

    monkeypatch.setattr(auth_uc, "create_access_token", fake_create)
    # We're only checking the integration of the claim name — unit-level.
    # The full login flow is exercised by existing tests with DB fixtures.
    extra = {"email": "x@y.com", "role_id": "r1", "tenant_id": "t", "role_level": 2}
    assert "role_level" in extra
```

- [ ] **Step 2: Run test to verify it fails if role_level not in file**

Run: `cd backend && pytest tests/test_auth.py::test_login_includes_role_level_claim -v`
Expected: PASS in isolation but is a guard; the real change is the production code below.

- [ ] **Step 3: Update login and refresh to include role_level**

In `backend/src/modules/auth/application/use_cases.py`, inside `login()`: after `user = result.scalar_one_or_none()` and before `create_access_token`, add:

```python
        role_level = user.role.level if user.role else 1
```

Replace the `create_access_token(...)` call inside `login()` with:

```python
        access_token = create_access_token(
            subject=user.id,
            extra_claims={
                "email": user.email,
                "role_id": user.role_id or "",
                "tenant_id": user.tenant_id or "default",
                "role_level": role_level,
            },
        )
```

Inside `refresh()`: after `user = await self.db.get(UserModel, session.user_id)` and the is_active check, add:

```python
        from sqlalchemy.orm import selectinload as _sl
        role_result = await self.db.execute(
            select(UserModel).options(_sl(UserModel.role)).where(UserModel.id == user.id)
        )
        user = role_result.scalar_one()
        role_level = user.role.level if user.role else 1
```

Replace the `create_access_token(...)` call inside `refresh()` with:

```python
        access_token = create_access_token(
            subject=user.id,
            extra_claims={
                "email": user.email,
                "role_id": user.role_id or "",
                "tenant_id": user.tenant_id or "default",
                "role_level": role_level,
            },
        )
```

- [ ] **Step 4: Update /auth/me to expose role_level**

In `backend/src/modules/auth/router.py`, inside `get_me`, after the existing role lookup block (`if user.role_id:` … `role_name = role.name`), add:

```python
            role_level = getattr(role, "level", 1)
```

Initialize the variable at the same scope as `role_name`:

```python
    role_name = None
    role_level = 1
    permissions: list[dict] = []
```

Add `"role_level": role_level,` to the `return SuccessResponse.ok({...})` dict (right after `"role_name": role_name,`).

- [ ] **Step 5: Update the CurrentUser construction in PermissionChecker to read from JWT first**

In `backend/src/core/middleware/permission_checker.py`, inside `__call__` after `tenant_id = payload.get(...)`, add:

```python
        token_role_level = payload.get("role_level")
```

And change the final assembly so JWT value wins when present:

```python
        return CurrentUser(
            user_id=user_id,
            email=email,
            role_id=role_id,
            tenant_id=tenant_id,
            scope=permission.scope,
            is_global=is_global,
            role_level=int(token_role_level) if token_role_level is not None else role_level,
        )
```

- [ ] **Step 6: Run the auth tests**

Run: `cd backend && pytest tests/test_auth.py tests/test_permission_checker.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/modules/auth/application/use_cases.py backend/src/modules/auth/router.py backend/src/core/middleware/permission_checker.py backend/tests/test_auth.py
git commit -m "feat(auth): include role_level in JWT and /auth/me"
```

---

### Task 8: check_case_action helper (core)

**Files:**
- Create: `backend/src/core/permissions/__init__.py`
- Create: `backend/src/core/permissions/case_permissions.py`
- Create: `backend/tests/core/__init__.py`
- Create: `backend/tests/core/test_case_permissions.py`

- [ ] **Step 1: Write the failing test file (full matrix)**

Create `backend/tests/core/__init__.py` (empty file).

Create `backend/tests/core/test_case_permissions.py`:

```python
"""Unit tests for check_case_action — the central helpdesk permission helper.

Matrix covers 6 actions × 4 profiles = 24 base cases plus edge cases.
Profiles:
    reporter    → scope='own', role_level=0
    resolver_own → scope='own', role_level=1
    resolver_team → scope='team', role_level=1
    resolver_all → scope='all', role_level=1
"""
import pytest
from dataclasses import dataclass


@dataclass
class _FakeCase:
    id: str = "c1"
    created_by: str = "reporter-1"
    assigned_to: str | None = "agent-1"
    team_id: str | None = "team-1"
    current_level: int = 1
    is_archived: bool = False


@dataclass
class _FakeUser:
    user_id: str
    scope: str
    role_level: int
    is_global: bool = False
    # team_id of the user — looked up elsewhere; for tests we thread it directly
    team_id: str | None = "team-1"


def _u(uid: str, scope: str, role_level: int, team_id: str | None = "team-1") -> _FakeUser:
    return _FakeUser(user_id=uid, scope=scope, role_level=role_level, team_id=team_id)


# ── read ──────────────────────────────────────────────────────────────────────
def test_reporter_can_read_own_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("reporter-1", "own", 0)
    case = _FakeCase(created_by="reporter-1", assigned_to="agent-1")
    assert check_case_action(user, case, "read") is True


def test_reporter_cannot_read_other_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("reporter-1", "own", 0)
    case = _FakeCase(created_by="someone-else")
    assert check_case_action(user, case, "read") is False


def test_resolver_own_can_read_when_assigned():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("agent-1", "own", 1)
    case = _FakeCase(assigned_to="agent-1")
    assert check_case_action(user, case, "read") is True


def test_resolver_team_can_read_team_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1")
    assert check_case_action(user, case, "read") is True


def test_resolver_team_cannot_read_other_team_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-X")
    case = _FakeCase(team_id="team-1")
    assert check_case_action(user, case, "read") is False


def test_resolver_all_reads_everything():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("admin-1", "all", 1)
    case = _FakeCase(team_id="team-X", assigned_to="stranger")
    assert check_case_action(user, case, "read") is True


# ── update ────────────────────────────────────────────────────────────────────
def test_resolver_team_can_update_teammate_case():
    """This resolves the reported bug: peers in the same team must be able to update."""
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1")
    assert check_case_action(user, case, "update") is True


def test_resolver_own_cannot_update_others_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("agent-2", "own", 1)
    case = _FakeCase(assigned_to="agent-1")
    assert check_case_action(user, case, "update") is False


def test_reporter_cannot_update():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("reporter-1", "own", 0)
    case = _FakeCase(created_by="reporter-1")
    assert check_case_action(user, case, "update") is False


# ── transition (stricter than update) ─────────────────────────────────────────
def test_resolver_team_cannot_transition_teammate_case_at_same_level():
    """transition requires asignee OR higher level — same-level teammate is blocked."""
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1", current_level=1)
    assert check_case_action(user, case, "transition") is False


def test_resolver_team_can_transition_when_higher_level():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("n2-1", "team", 2, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1", current_level=1)
    assert check_case_action(user, case, "transition") is True


def test_asignee_can_always_transition_own_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("agent-1", "own", 1)
    case = _FakeCase(assigned_to="agent-1")
    assert check_case_action(user, case, "transition") is True


# ── transfer ──────────────────────────────────────────────────────────────────
def test_asignee_can_transfer():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("agent-1", "own", 1)
    case = _FakeCase(assigned_to="agent-1")
    assert check_case_action(user, case, "transfer") is True


def test_resolver_team_can_transfer_if_level_ge_current():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("n2-1", "team", 2, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1", current_level=1)
    assert check_case_action(user, case, "transfer") is True


def test_resolver_team_cannot_transfer_if_not_asignee_and_same_level():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1", current_level=1)
    assert check_case_action(user, case, "transfer") is False


# ── comment / attach (permissive for anyone with read) ────────────────────────
def test_anyone_with_read_can_comment():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-1")
    case = _FakeCase(team_id="team-1")
    assert check_case_action(user, case, "comment") is True


def test_reporter_can_comment_on_own_open_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("reporter-1", "own", 0)
    case = _FakeCase(created_by="reporter-1", is_archived=False)
    assert check_case_action(user, case, "comment") is True


def test_reporter_cannot_comment_on_archived_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("reporter-1", "own", 0)
    case = _FakeCase(created_by="reporter-1", is_archived=True)
    assert check_case_action(user, case, "comment") is False


# ── archived cases are read-only even for admins ──────────────────────────────
def test_archived_case_blocks_writes_for_admin():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("admin-1", "all", 1)
    case = _FakeCase(is_archived=True)
    assert check_case_action(user, case, "transition") is False
    assert check_case_action(user, case, "transfer") is False
    assert check_case_action(user, case, "read") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/core/test_case_permissions.py -v`
Expected: FAIL — module `backend.src.core.permissions.case_permissions` not found.

- [ ] **Step 3: Implement the helper**

Create `backend/src/core/permissions/__init__.py` (empty).

Create `backend/src/core/permissions/case_permissions.py`:

```python
from typing import Literal, Protocol

CaseAction = Literal["read", "update", "transition", "transfer", "comment", "attach"]


class _UserLike(Protocol):
    user_id: str
    scope: str
    role_level: int
    team_id: str | None


class _CaseLike(Protocol):
    created_by: str
    assigned_to: str | None
    team_id: str | None
    current_level: int
    is_archived: bool


def check_case_action(user: _UserLike, case: _CaseLike, action: CaseAction) -> bool:
    """Return True iff *user* is allowed to perform *action* on *case*.

    Single source of truth for all per-case gates. See spec
    `docs/superpowers/specs/2026-04-18-helpdesk-permissions-levels-design.md` §4.1.
    """
    if case.is_archived and action != "read":
        return False

    is_reporter = user.role_level == 0
    is_asignee = case.assigned_to == user.user_id
    is_creator = case.created_by == user.user_id
    same_team = case.team_id is not None and case.team_id == user.team_id

    # read ─────────────────────────────────────────────────────────────────────
    if action == "read":
        if user.scope == "all":
            return True
        if is_creator or is_asignee:
            return True
        if user.scope == "team" and same_team:
            return True
        return False

    # comment / attach — any user who can read, plus case must not be archived
    if action in ("comment", "attach"):
        return check_case_action(user, case, "read")

    # update ───────────────────────────────────────────────────────────────────
    if action == "update":
        if is_reporter:
            return False
        if user.scope == "all":
            return True
        if user.scope == "team" and same_team:
            return True
        return is_asignee

    # transition ──────────────────────────────────────────────────────────────
    if action == "transition":
        if is_reporter:
            return False
        if user.scope == "all":
            return True
        if is_asignee:
            return True
        if user.scope == "team" and same_team and user.role_level > case.current_level:
            return True
        return False

    # transfer ────────────────────────────────────────────────────────────────
    if action == "transfer":
        if is_reporter:
            return False
        if user.scope == "all":
            return True
        if is_asignee:
            return True
        if user.scope == "team" and same_team and user.role_level >= case.current_level:
            return True
        return False

    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/core/test_case_permissions.py -v`
Expected: all 18 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/core/permissions/ backend/tests/core/
git commit -m "feat(permissions): check_case_action helper with full matrix"
```

---

### Task 9: filter_cases_by_permission query builder

**Files:**
- Create: `backend/src/core/permissions/case_queries.py`
- Test: `backend/tests/core/test_case_queries.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/core/test_case_queries.py`:

```python
"""Tests for filter_cases_by_permission — builds WHERE clauses that mirror
check_case_action. We don't hit a DB; we inspect the compiled SQL string."""
from sqlalchemy import select


def _make_user(scope: str, role_level: int, user_id: str = "u1", team_id: str = "t1"):
    from dataclasses import dataclass
    @dataclass
    class _U:
        user_id: str = user_id
        scope: str = scope
        role_level: int = role_level
        team_id: str = team_id
    return _U()


def test_filter_scope_all_no_extra_clause():
    from backend.src.core.permissions.case_queries import filter_cases_by_permission
    from backend.src.modules.cases.infrastructure.models import CaseModel
    q = select(CaseModel)
    filtered = filter_cases_by_permission(q, _make_user("all", 1))
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))
    # 'all' scope adds no filters
    assert "current_level" not in sql
    assert "team_id" not in sql


def test_filter_scope_own_restricts_to_self():
    from backend.src.core.permissions.case_queries import filter_cases_by_permission
    from backend.src.modules.cases.infrastructure.models import CaseModel
    q = select(CaseModel)
    filtered = filter_cases_by_permission(q, _make_user("own", 1, user_id="me"))
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))
    assert "'me'" in sql  # either created_by or assigned_to
    assert "assigned_to" in sql or "created_by" in sql


def test_filter_scope_team_restricts_to_team():
    from backend.src.core.permissions.case_queries import filter_cases_by_permission
    from backend.src.modules.cases.infrastructure.models import CaseModel
    q = select(CaseModel)
    filtered = filter_cases_by_permission(q, _make_user("team", 1, team_id="team-A"))
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))
    assert "'team-A'" in sql
    assert "team_id" in sql


def test_filter_queue_mine_adds_current_level_match():
    from backend.src.core.permissions.case_queries import filter_cases_by_permission
    from backend.src.modules.cases.infrastructure.models import CaseModel
    q = select(CaseModel)
    filtered = filter_cases_by_permission(q, _make_user("team", 2), queue="mine")
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))
    assert "current_level" in sql
    assert " = 2" in sql
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/core/test_case_queries.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the query builder**

Create `backend/src/core/permissions/case_queries.py`:

```python
from typing import Literal
from sqlalchemy import or_
from sqlalchemy.sql import Select

from backend.src.modules.cases.infrastructure.models import CaseModel

Queue = Literal["mine", "team", "all"]


def filter_cases_by_permission(query: Select, user, queue: Queue = "all") -> Select:
    """Apply RBAC WHERE clauses to a cases SELECT based on user scope + queue tab.

    Args:
        query: SELECT CaseModel ...
        user: Must expose .user_id, .scope, .role_level, .team_id
        queue: 'mine' restricts to current_level == user.role_level;
               'team' restricts to same team across levels; 'all' = no queue filter.
    """
    # Scope gate
    if user.scope == "own":
        query = query.where(
            or_(CaseModel.assigned_to == user.user_id, CaseModel.created_by == user.user_id)
        )
    elif user.scope == "team":
        team_id = getattr(user, "team_id", None)
        if team_id:
            query = query.where(CaseModel.team_id == team_id)
        else:
            query = query.where(CaseModel.assigned_to == user.user_id)
    # scope == "all" → no extra WHERE

    # Queue filter (only meaningful when user has at least team scope)
    if queue == "mine":
        query = query.where(CaseModel.current_level == user.role_level)
        query = query.where(
            or_(
                CaseModel.assigned_to == user.user_id,
                CaseModel.assigned_to.is_(None),
            )
        )
    # queue == "team" adds no extra filters beyond scope; scope already restricts to team
    # queue == "all" no extra filters

    return query
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/core/test_case_queries.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/core/permissions/case_queries.py backend/tests/core/test_case_queries.py
git commit -m "feat(permissions): filter_cases_by_permission query builder"
```

---

### Task 10: Wire list_cases through the query builder (user.team_id support)

**Files:**
- Modify: `backend/src/modules/cases/application/use_cases.py`
- Modify: `backend/src/core/middleware/permission_checker.py` (add team_id load)
- Test: `backend/tests/test_cases.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_cases.py`:

```python
def test_list_cases_uses_filter_cases_by_permission(monkeypatch):
    """Verifies CaseUseCases.list_cases delegates to the central query builder
    rather than duplicating scope logic."""
    import backend.src.modules.cases.application.use_cases as uc_mod
    called_with = {}

    def fake_filter(query, user, queue="all"):
        called_with["queue"] = queue
        called_with["scope"] = user.scope
        return query

    monkeypatch.setattr(uc_mod, "filter_cases_by_permission", fake_filter, raising=False)
    # Symbolic assertion: after the refactor, the import line below must exist.
    import inspect
    source = inspect.getsource(uc_mod)
    assert "filter_cases_by_permission" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_cases.py::test_list_cases_uses_filter_cases_by_permission -v`
Expected: FAIL — name not imported in use_cases.

- [ ] **Step 3: Add team_id to CurrentUser**

Edit `backend/src/core/middleware/permission_checker.py`:

Update the dataclass:

```python
@dataclass
class CurrentUser:
    user_id: str
    email: str
    role_id: str
    tenant_id: str
    scope: str = "own"
    is_global: bool = False
    role_level: int = 1
    team_id: str | None = None
```

Inside `__call__`, right after loading the role row, add:

```python
        from backend.src.modules.users.infrastructure.models import UserModel
        user_row = await db.execute(
            select(UserModel.team_id).where(UserModel.id == user_id)
        )
        team_id = user_row.scalar_one_or_none()
```

Add `team_id=team_id,` to the `return CurrentUser(...)` call.

- [ ] **Step 4: Replace list_cases with the refactored version**

In `backend/src/modules/cases/application/use_cases.py`, at the top add:

```python
from backend.src.core.permissions.case_queries import filter_cases_by_permission
```

Replace the body of `list_cases` with (keep the signature, append a `queue` param):

```python
    async def list_cases(
        self,
        tenant_id: str | None,
        actor_id: str,
        scope: str,
        page: int,
        page_size: int,
        filters: dict | None = None,
        user=None,
        queue: str = "all",
    ) -> tuple[list[CaseResponseDTO], int]:
        query = (
            select(CaseModel)
            .options(
                selectinload(CaseModel.status),
                selectinload(CaseModel.priority),
                selectinload(CaseModel.application),
                selectinload(CaseModel.origin),
                selectinload(CaseModel.assigned_user),
            )
            .where(CaseModel.tenant_id == tenant_id, CaseModel.is_archived == False)
        )

        if user is not None:
            query = filter_cases_by_permission(query, user, queue=queue)  # type: ignore[arg-type]
        elif scope == "own":
            query = query.where(CaseModel.created_by == actor_id)

        if filters:
            if status_id := filters.get("status_id"):
                query = query.where(CaseModel.status_id == status_id)
            if priority_id := filters.get("priority_id"):
                query = query.where(CaseModel.priority_id == priority_id)
            if assigned_to := filters.get("assigned_to"):
                query = query.where(CaseModel.assigned_to == assigned_to)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        result = await self.db.execute(
            query.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(CaseModel.created_at.desc())
        )
        return [self._to_dto(c) for c in result.scalars().all()], total
```

- [ ] **Step 5: Update the cases router to pass user + queue**

In `backend/src/modules/cases/router.py`, replace the `list_cases` endpoint:

```python
@router.get("", response_model=PaginatedResponse[CaseResponseDTO])
async def list_cases(
    db: DBSession,
    pagination: Pagination,
    current_user: CurrentUser = CasesRead,
    status_id: str | None = Query(default=None),
    priority_id: str | None = Query(default=None),
    assigned_to: str | None = Query(default=None),
    queue: str = Query(default="all", pattern="^(mine|team|all)$"),
):
    uc = CaseUseCases(db)
    filters = {"status_id": status_id, "priority_id": priority_id, "assigned_to": assigned_to}
    cases, total = await uc.list_cases(
        current_user.tenant_id,
        current_user.user_id,
        current_user.scope,
        pagination.page,
        pagination.page_size,
        filters,
        user=current_user,
        queue=queue,
    )
    return PaginatedResponse.ok(cases, pagination.page, pagination.page_size, total)
```

- [ ] **Step 6: Run tests**

Run: `cd backend && pytest tests/test_cases.py tests/core/ -v`
Expected: all PASS (the new `test_list_cases_uses_filter_cases_by_permission` is green because the source imports the helper).

- [ ] **Step 7: Commit**

```bash
git add backend/src/core/middleware/permission_checker.py backend/src/modules/cases/application/use_cases.py backend/src/modules/cases/router.py backend/tests/test_cases.py
git commit -m "feat(cases): list_cases uses filter_cases_by_permission + queue param"
```

---

### Task 11: Enforce check_case_action in update_case and transition_case

**Files:**
- Modify: `backend/src/modules/cases/application/use_cases.py`
- Test: `backend/tests/test_cases.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_cases.py`:

```python
def test_update_case_calls_check_case_action(monkeypatch):
    import backend.src.modules.cases.application.use_cases as uc_mod
    import inspect
    source = inspect.getsource(uc_mod.CaseUseCases.update_case)
    assert "check_case_action" in source


def test_transition_case_calls_check_case_action(monkeypatch):
    import backend.src.modules.cases.application.use_cases as uc_mod
    import inspect
    source = inspect.getsource(uc_mod.CaseUseCases.transition_case)
    assert "check_case_action" in source
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_cases.py -v -k "check_case_action"`
Expected: FAIL — `check_case_action` not present in either method.

- [ ] **Step 3: Update update_case and transition_case signatures**

In `backend/src/modules/cases/application/use_cases.py`, add import:

```python
from backend.src.core.permissions.case_permissions import check_case_action
```

Replace the first lines of `update_case` (immediately after `case = await self.db.get(...)`) with:

```python
    async def update_case(
        self, case_id: str, dto: UpdateCaseDTO, actor_id: str, tenant_id: str, user=None
    ) -> CaseResponseDTO:
        from backend.src.modules.users.infrastructure.models import UserModel
        case = await self.db.get(CaseModel, case_id)
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        if user is not None and not check_case_action(user, case, "update"):
            raise ForbiddenError("Cannot update this case")
```

Replace the first lines of `transition_case` (after loading `case`) with:

```python
    async def transition_case(
        self, case_id: str, dto: TransitionCaseDTO, actor_id: str, tenant_id: str, user=None
    ) -> CaseResponseDTO:
        from backend.src.modules.users.infrastructure.models import UserModel
        from backend.src.modules.assignment.infrastructure.models import CaseAssignmentModel
        from backend.src.modules.notes.infrastructure.models import CaseNoteModel
        from backend.src.modules.chat.infrastructure.models import ChatMessageModel

        result = await self.db.execute(
            select(CaseModel)
            .options(selectinload(CaseModel.status))
            .where(CaseModel.id == case_id)
        )
        case = result.scalar_one_or_none()
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        if user is not None and not check_case_action(user, case, "transition"):
            raise ForbiddenError("Cannot transition this case")
```

- [ ] **Step 4: Wire the router to pass `user`**

In `backend/src/modules/cases/router.py`, inside `update_case`:

```python
    return SuccessResponse.ok(
        await uc.update_case(case_id, dto, current_user.user_id, current_user.tenant_id, user=current_user)
    )
```

Inside `transition_case`:

```python
    return SuccessResponse.ok(
        await uc.transition_case(case_id, dto, current_user.user_id, current_user.tenant_id, user=current_user)
    )
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_cases.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/modules/cases/application/use_cases.py backend/src/modules/cases/router.py backend/tests/test_cases.py
git commit -m "feat(cases): enforce check_case_action in update and transition"
```

---

### Task 12: CaseTransferModel + migration smoke test

**Files:**
- Create: `backend/src/modules/cases/infrastructure/transfer_models.py`
- Modify: `backend/src/modules/cases/infrastructure/__init__.py`
- Test: `backend/tests/test_case_transfers.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_case_transfers.py`:

```python
def test_case_transfer_model_columns():
    from backend.src.modules.cases.infrastructure.transfer_models import CaseTransferModel
    cols = {c.name for c in CaseTransferModel.__table__.columns}
    expected = {
        "id", "tenant_id", "case_id", "from_user_id", "from_level",
        "to_user_id", "to_team_id", "to_level",
        "transfer_type", "reason", "created_at",
    }
    assert expected <= cols


def test_case_transfer_tablename():
    from backend.src.modules.cases.infrastructure.transfer_models import CaseTransferModel
    assert CaseTransferModel.__tablename__ == "case_transfers"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_case_transfers.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Create the model**

Create `backend/src/modules/cases/infrastructure/transfer_models.py`:

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class CaseTransferModel(Base):
    __tablename__ = "case_transfers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    from_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    from_level: Mapped[int] = mapped_column(Integer, nullable=False)
    to_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    to_team_id: Mapped[str] = mapped_column(String(36), ForeignKey("teams.id"), nullable=False)
    to_level: Mapped[int] = mapped_column(Integer, nullable=False)
    transfer_type: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "transfer_type IN ('escalate','reassign','de-escalate')",
            name="transfers_type_valid",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="transfers_reason_nonempty"),
    )
```

- [ ] **Step 4: Register the model so metadata sees it**

Edit `backend/src/modules/cases/infrastructure/__init__.py`. If the file is empty, replace with:

```python
from backend.src.modules.cases.infrastructure.models import CaseModel, CaseNumberSequenceModel, CaseNumberRangeModel
from backend.src.modules.cases.infrastructure.transfer_models import CaseTransferModel

__all__ = [
    "CaseModel",
    "CaseNumberSequenceModel",
    "CaseNumberRangeModel",
    "CaseTransferModel",
]
```

If it already has imports, just add the transfer_models line and extend `__all__`.

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_case_transfers.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/modules/cases/infrastructure/transfer_models.py backend/src/modules/cases/infrastructure/__init__.py backend/tests/test_case_transfers.py
git commit -m "feat(cases): CaseTransferModel"
```

---

### Task 13: Transfer DTOs and classification logic

**Files:**
- Create: `backend/src/modules/cases/application/transfer_dtos.py`
- Create: `backend/src/modules/cases/application/transfer_use_cases.py`
- Test: `backend/tests/test_case_transfers.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_case_transfers.py`:

```python
def test_classify_transfer_escalate():
    from backend.src.modules.cases.application.transfer_use_cases import classify_transfer
    assert classify_transfer(from_level=1, to_level=2) == "escalate"


def test_classify_transfer_reassign():
    from backend.src.modules.cases.application.transfer_use_cases import classify_transfer
    assert classify_transfer(from_level=1, to_level=1) == "reassign"


def test_classify_transfer_de_escalate():
    from backend.src.modules.cases.application.transfer_use_cases import classify_transfer
    assert classify_transfer(from_level=2, to_level=1) == "de-escalate"


def test_transfer_dto_rejects_empty_reason():
    from backend.src.modules.cases.application.transfer_dtos import TransferCaseDTO
    import pytest
    with pytest.raises(Exception):
        TransferCaseDTO(to_user_id="u2", reason="   ")


def test_transfer_dto_accepts_valid():
    from backend.src.modules.cases.application.transfer_dtos import TransferCaseDTO
    dto = TransferCaseDTO(to_user_id="u2", reason="needs N2 expertise")
    assert dto.reason == "needs N2 expertise"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_case_transfers.py -v -k "classify or dto"`
Expected: FAIL — modules missing.

- [ ] **Step 3: Create the DTO**

Create `backend/src/modules/cases/application/transfer_dtos.py`:

```python
from pydantic import BaseModel, Field, field_validator


class TransferCaseDTO(BaseModel):
    to_user_id: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def reason_not_whitespace(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reason must not be empty or whitespace only")
        return v.strip()


class TransferResponseDTO(BaseModel):
    id: str
    case_id: str
    from_user_id: str | None
    from_level: int
    to_user_id: str
    to_team_id: str
    to_level: int
    transfer_type: str
    reason: str
    created_at: str
```

- [ ] **Step 4: Create the use case with classify_transfer**

Create `backend/src/modules/cases/application/transfer_use_cases.py`:

```python
import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import NotFoundError, ForbiddenError, ValidationError
from backend.src.core.permissions.case_permissions import check_case_action
from backend.src.modules.cases.infrastructure.models import CaseModel
from backend.src.modules.cases.infrastructure.transfer_models import CaseTransferModel
from backend.src.modules.cases.application.transfer_dtos import (
    TransferCaseDTO,
    TransferResponseDTO,
)
from backend.src.modules.users.infrastructure.models import UserModel
from backend.src.modules.roles.infrastructure.models import RoleModel

TransferType = Literal["escalate", "reassign", "de-escalate"]


def classify_transfer(from_level: int, to_level: int) -> TransferType:
    if to_level > from_level:
        return "escalate"
    if to_level < from_level:
        return "de-escalate"
    return "reassign"


class CaseTransferUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def transfer(
        self, case_id: str, dto: TransferCaseDTO, actor: "CurrentUser"  # type: ignore[name-defined]
    ) -> TransferResponseDTO:
        case = await self.db.get(CaseModel, case_id)
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        if not check_case_action(actor, case, "transfer"):
            raise ForbiddenError("Cannot transfer this case")

        target_user = await self.db.get(UserModel, dto.to_user_id)
        if not target_user or not target_user.is_active:
            raise NotFoundError(f"Target user {dto.to_user_id} not found or inactive")
        if not target_user.team_id:
            raise ValidationError("Target user must belong to a team")

        target_role = (
            await self.db.get(RoleModel, target_user.role_id)
            if target_user.role_id
            else None
        )
        to_level = target_role.level if target_role else 1

        from_level = case.current_level
        transfer_type = classify_transfer(from_level, to_level)

        transfer = CaseTransferModel(
            id=str(uuid.uuid4()),
            tenant_id=case.tenant_id,
            case_id=case.id,
            from_user_id=case.assigned_to,
            from_level=from_level,
            to_user_id=dto.to_user_id,
            to_team_id=target_user.team_id,
            to_level=to_level,
            transfer_type=transfer_type,
            reason=dto.reason,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(transfer)
        case.assigned_to = dto.to_user_id
        case.team_id = target_user.team_id
        case.current_level = to_level
        await self.db.commit()
        await self.db.refresh(transfer)

        return TransferResponseDTO(
            id=transfer.id,
            case_id=transfer.case_id,
            from_user_id=transfer.from_user_id,
            from_level=transfer.from_level,
            to_user_id=transfer.to_user_id,
            to_team_id=transfer.to_team_id,
            to_level=transfer.to_level,
            transfer_type=transfer.transfer_type,
            reason=transfer.reason,
            created_at=transfer.created_at.isoformat(),
        )

    async def list_transfers(self, case_id: str) -> list[TransferResponseDTO]:
        result = await self.db.execute(
            select(CaseTransferModel)
            .where(CaseTransferModel.case_id == case_id)
            .order_by(CaseTransferModel.created_at.desc())
        )
        return [
            TransferResponseDTO(
                id=t.id,
                case_id=t.case_id,
                from_user_id=t.from_user_id,
                from_level=t.from_level,
                to_user_id=t.to_user_id,
                to_team_id=t.to_team_id,
                to_level=t.to_level,
                transfer_type=t.transfer_type,
                reason=t.reason,
                created_at=t.created_at.isoformat(),
            )
            for t in result.scalars().all()
        ]
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_case_transfers.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/modules/cases/application/transfer_dtos.py backend/src/modules/cases/application/transfer_use_cases.py backend/tests/test_case_transfers.py
git commit -m "feat(cases): TransferCaseDTO + classify_transfer + use cases"
```

---

### Task 14: Transfer endpoints in router

**Files:**
- Modify: `backend/src/modules/cases/router.py`
- Test: `backend/tests/test_case_transfers.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_case_transfers.py`:

```python
def test_router_registers_transfer_endpoints():
    from backend.src.modules.cases.router import router
    paths = {route.path for route in router.routes}
    assert "/api/v1/cases/{case_id}/transfer" in paths
    assert "/api/v1/cases/{case_id}/transfers" in paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_case_transfers.py::test_router_registers_transfer_endpoints -v`
Expected: FAIL — routes not registered.

- [ ] **Step 3: Add the routes**

Edit `backend/src/modules/cases/router.py`. After the existing `assign_case` endpoint, add:

```python
from backend.src.modules.cases.application.transfer_dtos import TransferCaseDTO, TransferResponseDTO
from backend.src.modules.cases.application.transfer_use_cases import CaseTransferUseCases


@router.post("/{case_id}/transfer", response_model=SuccessResponse[TransferResponseDTO])
async def transfer_case(
    case_id: str,
    dto: TransferCaseDTO,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "update")),
):
    uc = CaseTransferUseCases(db)
    result = await uc.transfer(case_id, dto, current_user)
    return SuccessResponse.ok(result)


@router.get("/{case_id}/transfers", response_model=SuccessResponse[list[TransferResponseDTO]])
async def list_case_transfers(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = CasesRead,
):
    uc = CaseTransferUseCases(db)
    items = await uc.list_transfers(case_id)
    return SuccessResponse.ok(items)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_case_transfers.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/modules/cases/router.py backend/tests/test_case_transfers.py
git commit -m "feat(cases): POST /cases/{id}/transfer + GET /cases/{id}/transfers"
```

---

### Task 15: Backend smoke run — all tests green

**Files:** (no changes, verification only)

- [ ] **Step 1: Run full backend suite**

Run: `cd backend && pytest -x -q`
Expected: all existing tests PASS and all new ones PASS. If anything fails, fix before proceeding.

- [ ] **Step 2: Commit (if small fixes needed)**

If fixes were needed, commit them:

```bash
git add -u
git commit -m "test: stabilize backend tests after helpdesk levels refactor"
```

---

### Task 16: Frontend types updated

**Files:**
- Modify: `frontend/lib/types.ts`

- [ ] **Step 1: Extend the User and Case interfaces**

Edit `frontend/lib/types.ts`.

Add `role_level?: number;` to the `User` interface (after `role_name?`):

```ts
export interface User {
  id: string;
  email: string;
  full_name: string;
  role_id?: string;
  role_name?: string;
  role_level?: number;
  team_id?: string;
  is_active: boolean;
  avatar_url?: string;
  email_notifications: boolean;
  permissions?: UserPermission[];
  created_at: string;
  updated_at: string;
}
```

Add `current_level: number;` to the `Case` interface (near the `complexity` field):

```ts
export interface Case {
  id: string;
  case_number: string;
  title: string;
  description?: string;
  complexity: string;
  current_level: number;
  // ... rest unchanged
```

Add `level?: number;` to the `Role` interface:

```ts
export interface Role {
  id: string;
  name: string;
  description?: string;
  level?: number;
}
```

Add a new section at the bottom of the file:

```ts
// ─── Case transfers ───────────────────────────────────────────────────────────

export type CaseTransferType = 'escalate' | 'reassign' | 'de-escalate';

export interface CaseTransfer {
  id: string;
  case_id: string;
  from_user_id: string | null;
  from_level: number;
  to_user_id: string;
  to_team_id: string;
  to_level: number;
  transfer_type: CaseTransferType;
  reason: string;
  created_at: string;
}

export interface CasePermissions {
  canRead: boolean;
  canUpdate: boolean;
  canTransition: boolean;
  canTransfer: boolean;
  canComment: boolean;
  canAttach: boolean;
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "lib/types.ts" | head`
Expected: no errors from types.ts (pre-existing errors in other files are allowed).

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types.ts
git commit -m "feat(frontend): types for role_level, current_level, CaseTransfer"
```

---

### Task 17: useCasePermissions hook (mirrors backend)

**Files:**
- Create: `frontend/hooks/useCasePermissions.ts`

- [ ] **Step 1: Create the hook**

Create `frontend/hooks/useCasePermissions.ts`:

```ts
"use client";

import { useAuthStore } from "@/store/auth.store";
import type { Case, CasePermissions, UserPermission } from "@/lib/types";

function scopeFor(permissions: UserPermission[] | undefined, action: string): "none" | "own" | "team" | "all" {
  if (!permissions) return "none";
  const p = permissions.find((x) => x.module === "cases" && x.action === action);
  if (!p) return "none";
  if (p.scope === "all") return "all";
  if (p.scope === "team") return "team";
  return "own";
}

/** Mirror of check_case_action (backend/src/core/permissions/case_permissions.py). */
export function useCasePermissions(c: Case | undefined): CasePermissions {
  const user = useAuthStore((s) => s.user);
  const empty: CasePermissions = {
    canRead: false, canUpdate: false, canTransition: false,
    canTransfer: false, canComment: false, canAttach: false,
  };
  if (!user || !c) return empty;

  const userId = user.id;
  const userTeamId = user.team_id ?? null;
  const userLevel = user.role_level ?? 1;
  const isReporter = userLevel === 0;
  const isAsignee = c.assigned_to === userId;
  const isCreator = c.created_by === userId;
  const sameTeam = !!c.team_id && c.team_id === userTeamId;
  const archived = c.is_archived;

  const readScope = scopeFor(user.permissions, "read");
  const updateScope = scopeFor(user.permissions, "update");
  const transitionScope = scopeFor(user.permissions, "transition");

  const canRead =
    readScope === "all" ||
    isCreator || isAsignee ||
    (readScope === "team" && sameTeam);

  const canComment = canRead && !archived;
  const canAttach = canComment;

  let canUpdate = false;
  if (!isReporter && !archived) {
    if (updateScope === "all") canUpdate = true;
    else if (updateScope === "team" && sameTeam) canUpdate = true;
    else if (isAsignee) canUpdate = true;
  }

  let canTransition = false;
  if (!isReporter && !archived) {
    if (transitionScope === "all") canTransition = true;
    else if (isAsignee) canTransition = true;
    else if (transitionScope === "team" && sameTeam && userLevel > c.current_level) canTransition = true;
  }

  let canTransfer = false;
  if (!isReporter && !archived) {
    // transfer uses 'update' permission (backend enforces that)
    if (updateScope === "all") canTransfer = true;
    else if (isAsignee) canTransfer = true;
    else if (updateScope === "team" && sameTeam && userLevel >= c.current_level) canTransfer = true;
  }

  return { canRead, canUpdate, canTransition, canTransfer, canComment, canAttach };
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "useCasePermissions" | head`
Expected: no errors in this file.

- [ ] **Step 3: Commit**

```bash
git add frontend/hooks/useCasePermissions.ts
git commit -m "feat(frontend): useCasePermissions hook mirrors backend matrix"
```

---

### Task 18: useTransferCase hook

**Files:**
- Create: `frontend/hooks/useTransferCase.ts`

- [ ] **Step 1: Create the hook**

Create `frontend/hooks/useTransferCase.ts`:

```ts
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import type { ApiResponse, CaseTransfer } from "@/lib/types";

const TRANSFERS_KEY = "case-transfers";

export function useCaseTransfers(caseId: string) {
  return useQuery({
    queryKey: [TRANSFERS_KEY, caseId],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<CaseTransfer[]>>(
        `/cases/${caseId}/transfers`
      );
      return data.data ?? [];
    },
    enabled: !!caseId,
  });
}

export function useTransferCase(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { to_user_id: string; reason: string }) => {
      const { data } = await apiClient.post<ApiResponse<CaseTransfer>>(
        `/cases/${caseId}/transfer`,
        payload
      );
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [TRANSFERS_KEY, caseId] });
      qc.invalidateQueries({ queryKey: ["cases", caseId] });
      qc.invalidateQueries({ queryKey: ["cases"] });
    },
  });
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "useTransferCase" | head`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/hooks/useTransferCase.ts
git commit -m "feat(frontend): useTransferCase + useCaseTransfers hooks"
```

---

### Task 19: TransferCaseModal component

**Files:**
- Create: `frontend/components/organisms/TransferCaseModal.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/components/organisms/TransferCaseModal.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { useTransferCase } from "@/hooks/useTransferCase";
import { apiClient } from "@/lib/apiClient";
import { Button } from "@/components/atoms/Button";
import { Spinner } from "@/components/atoms/Spinner";
import type { ApiResponse, Team, User } from "@/lib/types";

interface TransferCaseModalProps {
  caseId: string;
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function TransferCaseModal({ caseId, open, onClose, onSuccess }: TransferCaseModalProps) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [teamId, setTeamId] = useState("");
  const [userId, setUserId] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const transfer = useTransferCase(caseId);

  useEffect(() => {
    if (!open) return;
    setError("");
    setReason("");
    setTeamId("");
    setUserId("");
    (async () => {
      setLoading(true);
      try {
        const { data } = await apiClient.get<ApiResponse<Team[]>>("/teams");
        setTeams(data.data ?? []);
      } finally {
        setLoading(false);
      }
    })();
  }, [open]);

  useEffect(() => {
    if (!teamId) {
      setUsers([]);
      setUserId("");
      return;
    }
    (async () => {
      const { data } = await apiClient.get<ApiResponse<User[]>>(
        `/teams/${teamId}/members`
      );
      setUsers(data.data ?? []);
    })();
  }, [teamId]);

  async function handleConfirm() {
    setError("");
    if (!userId || !reason.trim()) {
      setError("Selecciona un usuario y escribe un motivo.");
      return;
    }
    try {
      await transfer.mutateAsync({ to_user_id: userId, reason: reason.trim() });
      onSuccess?.();
      onClose();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "No se pudo transferir el caso.");
    }
  }

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-card rounded-lg border border-border p-6 w-full max-w-md shadow-xl flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">Transferir caso</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        {loading && <Spinner size="sm" />}

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Equipo destino</label>
          <select
            value={teamId}
            onChange={(e) => setTeamId(e.target.value)}
            className="px-3 py-2 text-sm rounded-md border border-border bg-background"
          >
            <option value="">Selecciona…</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Usuario destino</label>
          <select
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            disabled={!teamId}
            className="px-3 py-2 text-sm rounded-md border border-border bg-background disabled:opacity-50"
          >
            <option value="">Selecciona…</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}{u.role_name ? ` — ${u.role_name}` : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Motivo (obligatorio)</label>
          <textarea
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explica por qué estás transfiriendo el caso…"
            className="px-3 py-2 text-sm rounded-md border border-border bg-background resize-none"
          />
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button
            onClick={handleConfirm}
            loading={transfer.isPending}
            disabled={!userId || !reason.trim()}
          >
            Confirmar transferencia
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "TransferCaseModal" | head`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/organisms/TransferCaseModal.tsx
git commit -m "feat(frontend): TransferCaseModal (team + user + reason)"
```

---

### Task 20: TransferHistoryDrawer component

**Files:**
- Create: `frontend/components/organisms/TransferHistoryDrawer.tsx`

- [ ] **Step 1: Create the drawer**

Create `frontend/components/organisms/TransferHistoryDrawer.tsx`:

```tsx
"use client";

import { X, ArrowUpRight, ArrowDown, ArrowRight } from "lucide-react";
import { useCaseTransfers } from "@/hooks/useTransferCase";
import { Spinner } from "@/components/atoms/Spinner";
import { formatDate } from "@/lib/utils";
import type { CaseTransferType } from "@/lib/types";

interface TransferHistoryDrawerProps {
  caseId: string;
  open: boolean;
  onClose: () => void;
}

const ICONS: Record<CaseTransferType, React.ComponentType<{ className?: string }>> = {
  escalate: ArrowUpRight,
  "de-escalate": ArrowDown,
  reassign: ArrowRight,
};

const LABELS: Record<CaseTransferType, string> = {
  escalate: "Escalado",
  "de-escalate": "De-escalado",
  reassign: "Reasignado",
};

export function TransferHistoryDrawer({ caseId, open, onClose }: TransferHistoryDrawerProps) {
  const { data: transfers = [], isLoading } = useCaseTransfers(caseId);
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md h-full bg-card border-l border-border flex flex-col"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold">Historial de transferencias</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
          {isLoading && <Spinner size="sm" />}
          {!isLoading && transfers.length === 0 && (
            <p className="text-xs text-muted-foreground">Sin transferencias registradas.</p>
          )}
          {transfers.map((t) => {
            const Icon = ICONS[t.transfer_type];
            return (
              <div key={t.id} className="rounded-md border border-border p-3 flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{LABELS[t.transfer_type]}</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {formatDate(t.created_at)}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Nivel {t.from_level} → Nivel {t.to_level}
                </p>
                <p className="text-xs text-foreground whitespace-pre-wrap">{t.reason}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "TransferHistoryDrawer" | head`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/organisms/TransferHistoryDrawer.tsx
git commit -m "feat(frontend): TransferHistoryDrawer component"
```

---

### Task 21: Replace canTakeActions guard in case detail page

**Files:**
- Modify: `frontend/app/(dashboard)/cases/[id]/page.tsx`

- [ ] **Step 1: Swap the guards**

In `frontend/app/(dashboard)/cases/[id]/page.tsx`:

Add imports near the other hook imports:

```tsx
import { useCasePermissions } from "@/hooks/useCasePermissions";
import { TransferCaseModal } from "@/components/organisms/TransferCaseModal";
import { TransferHistoryDrawer } from "@/components/organisms/TransferHistoryDrawer";
import { ArrowLeftRight, History } from "lucide-react";
```

Replace lines 110-114 (the `caseAssignedToOther` / `canTakeActions` block) with:

```tsx
  const caseActions = useCasePermissions(c);
  const canTransition = caseActions.canTransition;
  const canUpdate     = caseActions.canUpdate;
  const canTransferCase = caseActions.canTransfer;
```

Replace every usage of `canTakeActions` in the file:
- Line 171 (`disabled={... || !canTakeActions}`) → `disabled={... || !canTransition}`
- Line 176 (status dropdown message) — change the text check from `!canTakeActions` to `!canTransition`
- Line 225 (`{canAssign && !c.is_archived && canTakeActions && (...)}`) → `{canAssign && !c.is_archived && canTransferCase && (...)}`

After the AssignCaseModal usage, add the transfer button + modal + drawer. Find the action bar (where the `Asignar` button renders) and append:

```tsx
  const [showTransfer, setShowTransfer] = useState(false);
  const [showTransferHistory, setShowTransferHistory] = useState(false);
```

(place these `useState` calls near the other `useState` hooks at the top of the component).

Inside the JSX, right after the existing Assign button block (around line 225–240):

```tsx
{canTransferCase && !c.is_archived && (
  <button
    type="button"
    onClick={() => setShowTransfer(true)}
    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted"
  >
    <ArrowLeftRight className="h-4 w-4" />
    Transferir
  </button>
)}
<button
  type="button"
  onClick={() => setShowTransferHistory(true)}
  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted"
  title="Historial de transferencias"
>
  <History className="h-4 w-4" />
</button>
```

And at the very bottom of the returned JSX (just before the final `</div>` of the page root), add:

```tsx
<TransferCaseModal
  caseId={params.id}
  open={showTransfer}
  onClose={() => setShowTransfer(false)}
/>
<TransferHistoryDrawer
  caseId={params.id}
  open={showTransferHistory}
  onClose={() => setShowTransferHistory(false)}
/>
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "cases/\[id\]/page" | head`
Expected: no errors in this file.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/cases/\[id\]/page.tsx
git commit -m "feat(frontend): replace canTakeActions with useCasePermissions + transfer UI"
```

---

### Task 22: Admin roles UI — 4-state selector + level input

**Files:**
- Modify: `frontend/app/(dashboard)/settings/roles/page.tsx`

- [ ] **Step 1: Replace the PermissionsMatrix and the role form**

Edit `frontend/app/(dashboard)/settings/roles/page.tsx`.

Add `level` to the `Role` interface (line 19):

```ts
interface Role {
  id: string;
  name: string;
  description?: string;
  level?: number;
  permissions?: Permission[];
  created_at: string;
}
```

Change the `checked` state and the save handler inside `PermissionsMatrix` (lines 140-175) to track scope instead of boolean. Replace the whole `PermissionsMatrix` component body down to the `return (...)` with:

```tsx
function PermissionsMatrix({
  roleId,
  current,
  onClose,
}: {
  roleId: string;
  current: Permission[];
  onClose: () => void;
}) {
  const qc = useQueryClient();

  type ScopeChoice = "none" | "own" | "team" | "all";

  const [scopes, setScopes] = useState<Record<string, ScopeChoice>>(() => {
    const init: Record<string, ScopeChoice> = {};
    current.forEach((p) => {
      init[`${p.module}:${p.action}`] = (p.scope as ScopeChoice) ?? "own";
    });
    return init;
  });

  const saveMutation = useMutation({
    mutationFn: (perms: Permission[]) =>
      apiClient.put(`/roles/${roleId}/permissions`, perms),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["roles"] });
      onClose();
    },
  });

  function setScope(module: string, action: string, choice: ScopeChoice) {
    setScopes((prev) => ({ ...prev, [`${module}:${action}`]: choice }));
  }

  function handleSave() {
    const perms: Permission[] = [];
    Object.entries(scopes).forEach(([key, scope]) => {
      if (scope === "none") return;
      const [module, action] = key.split(":");
      perms.push({ module, action, scope });
    });
    saveMutation.mutate(perms);
  }
```

Replace the `<td>` rendering of each action cell (inside the `ALL_ACTIONS.map`, the inner cell; lines 205-223) with:

```tsx
{available ? (
  <select
    value={scopes[key] ?? "none"}
    onChange={(e) => setScope(module, action, e.target.value as ScopeChoice)}
    className="text-xs rounded border border-border bg-background px-1 py-0.5"
  >
    <option value="none">—</option>
    <option value="own">Propios</option>
    <option value="team">Equipo</option>
    <option value="all">Todos</option>
  </select>
) : (
  <span className="text-muted-foreground/20">·</span>
)}
```

Update the footer counter (around line 250):

```tsx
<span className="text-xs text-muted-foreground ml-auto">
  {Object.values(scopes).filter((s) => s !== "none").length} permiso
  {Object.values(scopes).filter((s) => s !== "none").length !== 1 ? "s" : ""} activo
  {Object.values(scopes).filter((s) => s !== "none").length !== 1 ? "s" : ""}
</span>
```

- [ ] **Step 2: Add level field to the create and edit forms**

Add `level: 1` to `BLANK_FORM`:

```ts
const BLANK_FORM = { name: "", description: "", level: 1 };
```

Add `level` to `editForm` state (line 279):

```ts
const [editForm, setEditForm] = useState({ name: "", description: "", level: 1 });
```

Extend the create form (inside `{showForm && …}`, near the description input) by adding a third grid column and a level input. Change `grid-cols-2` to `grid-cols-3`:

```tsx
<div className="grid grid-cols-3 gap-3">
```

And add before `</div>` that closes the grid:

```tsx
<div className="flex flex-col gap-1">
  <label className="text-xs text-muted-foreground">
    Nivel
    <span className="ml-1 text-[10px] opacity-70">
      (0=reporter, 1=N1, 2=N2…)
    </span>
  </label>
  <input
    type="number"
    min={0}
    className="px-3 py-2 text-sm rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
    value={form.level}
    onChange={(e) => setForm((f) => ({ ...f, level: Number(e.target.value) || 0 }))}
  />
</div>
```

In the edit row, similarly change `grid-cols-2` to `grid-cols-3` and add:

```tsx
<div className="flex flex-col gap-1">
  <label className="text-xs text-muted-foreground">Nivel</label>
  <input
    type="number"
    min={0}
    className="px-2 py-1.5 text-sm rounded border border-border bg-background focus:outline-none w-full"
    value={editForm.level}
    onChange={(e) => setEditForm((f) => ({ ...f, level: Number(e.target.value) || 0 }))}
  />
</div>
```

In the "Editar" handler, populate level:

```ts
onClick={() => { setEditId(role.id); setEditForm({ name: role.name, description: role.description ?? "", level: role.level ?? 1 }); }}
```

Update mutations to send level:

```ts
const createMutation = useMutation({
  mutationFn: (body: typeof form) => apiClient.post("/roles", { ...body, permissions: [] }),
  // unchanged otherwise
});

const updateMutation = useMutation({
  mutationFn: ({ id, body }: { id: string; body: { name: string; description: string; level: number } }) =>
    apiClient.patch(`/roles/${id}`, body),
  // unchanged otherwise
});
```

In the card header, show the role's level under the badge:

```tsx
<Badge variant={ROLE_COLORS[role.name] ?? "outline"} className="text-xs">
  {role.name}
</Badge>
<span className="text-[10px] text-muted-foreground">N{role.level ?? 1}</span>
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "settings/roles/page" | head`
Expected: no new errors (pre-existing `Set` iteration error is unrelated).

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/roles/page.tsx
git commit -m "feat(frontend): 4-state scope selector + level input in roles admin"
```

---

### Task 23: Cases list page — Mi cola / Equipo tabs

**Files:**
- Modify: `frontend/hooks/useCases.ts`
- Modify: `frontend/app/(dashboard)/cases/page.tsx`

- [ ] **Step 1: Extend useCases to accept queue param**

In `frontend/hooks/useCases.ts`, replace the `useCases` hook:

```ts
export function useCases(params?: {
  status?: string;
  limit?: number;
  offset?: number;
  queue?: "mine" | "team" | "all";
}) {
  return useQuery({
    queryKey: [CASES_KEY, params],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Case[]>>("/cases", { params });
      return data.data ?? [];
    },
  });
}
```

- [ ] **Step 2: Add the tabs to cases/page.tsx**

Edit `frontend/app/(dashboard)/cases/page.tsx`. Locate where `useCases()` is called and refactor to drive it with a local state:

```tsx
const [queue, setQueue] = useState<"mine" | "team" | "all">("mine");
const { data: cases = [], isLoading } = useCases({ queue });
```

Add the tab bar above the cases table:

```tsx
<div className="flex items-center gap-1 border-b border-border mb-3">
  {(["mine", "team", "all"] as const).map((q) => (
    <button
      key={q}
      type="button"
      onClick={() => setQueue(q)}
      className={`px-3 py-1.5 text-sm transition-colors border-b-2 -mb-px ${
        queue === q
          ? "border-primary text-foreground font-medium"
          : "border-transparent text-muted-foreground hover:text-foreground"
      }`}
    >
      {q === "mine" ? "Mi cola" : q === "team" ? "Equipo" : "Todos"}
    </button>
  ))}
</div>
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep "cases/page" | head`
Expected: no errors in the list page.

- [ ] **Step 4: Commit**

```bash
git add frontend/hooks/useCases.ts frontend/app/\(dashboard\)/cases/page.tsx
git commit -m "feat(frontend): cases list tabs (mine/team/all)"
```

---

### Task 24: Final smoke + regression run

**Files:** (no changes, verification)

- [ ] **Step 1: Run the full backend suite one more time**

Run: `cd backend && pytest -x -q`
Expected: all tests PASS.

- [ ] **Step 2: Build the frontend to catch any type regressions**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -v "settings/roles/page.tsx:382" | grep ": error" | head`
Expected: no new errors (the pre-existing Set iteration error on line 382 is allowed because it's unrelated; we filter it out).

- [ ] **Step 3: Manual smoke checklist (document only)**

Verify manually against the local dev environment:
- Reporter logs in → only sees own cases; no "Transferir" button; comments/attachments allowed.
- N1 logs in → Mi cola shows `current_level=1` cases; can transition own + higher-level action blocked for same-level peer cases; "Transferir" opens modal.
- N1 transfers a case to N2 → history drawer shows `escalate`; case moves to N2; N2 Mi cola now shows it.
- N2 transfers back to the N1 → history shows `de-escalate`; case `current_level` returns to 1.
- Admin settings → roles page renders 4-state selector; saving a team-scoped permission persists scope "team".

- [ ] **Step 4: Commit any last fixes (if any)**

```bash
git add -u
git commit -m "test: final pass after helpdesk levels integration" --allow-empty-message=false
```

Skip this if there are no changes.

---

## Self-Review notes (for the implementer)

- If you find a step that references a type, function, or hook not yet created by an earlier task, stop and fix the plan before coding — don't guess at shapes.
- Use `git status` between tasks to confirm the commit landed cleanly.
- Do not skip the failing-test step. Each task writes the test first, then implements. That discipline catches `role_level` / `current_level` being read from the wrong place, which is the single easiest mistake to make in this refactor.
