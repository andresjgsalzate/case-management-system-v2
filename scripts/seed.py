"""
Database seed script.
Run from the project root:
    python scripts/seed.py

Requires DATABASE_URL and SECRET_KEY in backend/.env
"""
import asyncio
import os
import sys

# Project root must be on sys.path so "backend.src.*" imports work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, "backend", ".env"))
except ImportError:
    pass

import uuid

from backend.src.core.config import get_settings
from backend.src.core.database import AsyncSessionLocal
from backend.src.core.security import hash_password

# Import ALL models up-front so SQLAlchemy relationship resolution works
from backend.src.modules.roles.infrastructure.models import RoleModel, PermissionModel
from backend.src.modules.users.infrastructure.models import UserModel
from backend.src.modules.auth.infrastructure.models import UserSessionModel  # needed for UserModel.sessions relationship
from backend.src.modules.teams.infrastructure.models import TeamModel, TeamMemberModel
from backend.src.modules.case_statuses.infrastructure.models import CaseStatusModel
from backend.src.modules.case_priorities.infrastructure.models import CasePriorityModel
from backend.src.modules.applications.infrastructure.models import ApplicationModel
from backend.src.modules.origins.infrastructure.models import OriginModel
from backend.src.modules.cases.infrastructure.models import CaseNumberSequenceModel, CaseModel
from backend.src.modules.assignment.infrastructure.models import CaseAssignmentModel
from backend.src.modules.activity.infrastructure.models import ActivityEntryModel
from backend.src.modules.classification.infrastructure.models import CaseClassificationModel, ClassificationRuleModel
from backend.src.modules.sla.infrastructure.models import SLAPolicyModel, SLARecordModel, SLAHolidayModel, SLAWorkScheduleModel
from backend.src.modules.chat.infrastructure.models import ChatMessageModel
from backend.src.modules.notes.infrastructure.models import CaseNoteModel
from backend.src.modules.attachments.infrastructure.models import CaseAttachmentModel
from backend.src.modules.todos.infrastructure.models import CaseTodoModel
from backend.src.modules.time_entries.infrastructure.models import TimeEntryModel, ActiveTimerModel
from backend.src.modules.dispositions.infrastructure.models import DispositionCategoryModel, DispositionModel
from backend.src.modules.knowledge_base.infrastructure.models import (
    KBTagModel, KBArticleModel, KBArticleTagModel,
    KBArticleVersionModel, KBReviewEventModel, KBFavoriteModel, KBFeedbackModel,
)
from backend.src.modules.notifications.infrastructure.models import NotificationModel
from backend.src.modules.audit.infrastructure.models import AuditLogModel
from backend.src.modules.automation.infrastructure.models import AutomationRuleModel


async def verify_connection() -> bool:
    """Verify PostgreSQL connectivity before seeding."""
    from sqlalchemy import text
    settings = get_settings()
    db_display = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "localhost"
    print(f"Connecting to: {db_display}")
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
        print("OK - Database connection OK")
        return True
    except Exception as exc:
        print(f"ERROR - Database connection failed: {exc}")
        return False


MODULES = [
    "cases", "users", "teams", "roles", "sla", "knowledge", "audit",
    "metrics", "dispositions", "todos", "notes", "time", "classification",
    "attachments", "notifications", "automation", "applications", "origins",
]

ROLES_SEED = [
    {
        "name": "Super Admin",
        "description": "Acceso total al sistema",
        "permissions": [
            {"module": m, "action": a, "scope": "all"}
            for m in MODULES
            for a in [
                "create", "read", "update", "delete", "manage", "export",
                "archive", "assign", "publish", "transition", "review", "publish_direct",
            ]
        ],
    },
    {
        "name": "Admin",
        "description": "Administrador del sistema",
        "permissions": [
            {"module": m, "action": a, "scope": "all"}
            for m in MODULES if m != "roles"
            for a in ["create", "read", "update", "delete", "manage", "export"]
        ],
    },
    {
        "name": "Manager",
        "description": "Manager de equipos",
        "permissions": [
            {"module": "cases", "action": "read", "scope": "all"},
            {"module": "cases", "action": "assign", "scope": "all"},
            {"module": "metrics", "action": "read", "scope": "all"},
            {"module": "teams", "action": "manage", "scope": "all"},
            {"module": "audit", "action": "read", "scope": "all"},
            {"module": "knowledge", "action": "read", "scope": "all"},
            {"module": "knowledge", "action": "review", "scope": "all"},
            {"module": "dispositions", "action": "manage", "scope": "all"},
            {"module": "sla", "action": "read", "scope": "all"},
        ],
    },
    {
        "name": "Agent",
        "description": "Agente de soporte",
        "permissions": [
            {"module": "cases", "action": "create", "scope": "own"},
            {"module": "cases", "action": "read", "scope": "team"},
            {"module": "cases", "action": "update", "scope": "own"},
            {"module": "cases", "action": "transition", "scope": "own"},
            {"module": "todos", "action": "create", "scope": "own"},
            {"module": "todos", "action": "read", "scope": "own"},
            {"module": "todos", "action": "update", "scope": "own"},
            {"module": "notes", "action": "create", "scope": "own"},
            {"module": "notes", "action": "read", "scope": "team"},
            {"module": "time", "action": "create", "scope": "own"},
            {"module": "time", "action": "read", "scope": "own"},
            {"module": "knowledge", "action": "read", "scope": "all"},
            {"module": "notifications", "action": "read", "scope": "own"},
            {"module": "attachments", "action": "create", "scope": "own"},
            {"module": "attachments", "action": "read", "scope": "team"},
        ],
    },
]


async def seed_phase_1(session) -> None:
    """Seed roles, permissions, and admin user."""
    from sqlalchemy import select

    role_map: dict[str, str] = {}

    for role_data in ROLES_SEED:
        existing = await session.execute(
            select(RoleModel).where(
                RoleModel.name == role_data["name"],
                RoleModel.tenant_id == None,
            )
        )
        existing_role = existing.scalar_one_or_none()
        if existing_role:
            role_map[role_data["name"]] = existing_role.id
            print(f"  Role '{role_data['name']}' already exists - skipping")
            continue

        role_id = str(uuid.uuid4())
        role = RoleModel(
            id=role_id,
            tenant_id=None,
            name=role_data["name"],
            description=role_data["description"],
        )
        session.add(role)
        await session.flush()

        for perm in role_data["permissions"]:
            p = PermissionModel(
                id=str(uuid.uuid4()),
                role_id=role_id,
                module=perm["module"],
                action=perm["action"],
                scope=perm["scope"],
            )
            session.add(p)

        role_map[role_data["name"]] = role_id
        print(f"  + Role '{role_data['name']}' created with {len(role_data['permissions'])} permissions")

    # Admin user
    admin_email = "admin@example.com"
    existing_admin = await session.execute(
        select(UserModel).where(UserModel.email == admin_email)
    )
    if existing_admin.scalar_one_or_none():
        print("  Admin user already exists - skipping")
    else:
        admin_role_id = role_map.get("Super Admin")
        admin = UserModel(
            id=str(uuid.uuid4()),
            tenant_id=None,
            email=admin_email,
            full_name="System Administrator",
            hashed_password=hash_password("ChangeMe123!"),
            role_id=admin_role_id,
            is_active=True,
        )
        session.add(admin)
        print(f"  + Admin user created: {admin_email} / ChangeMe123!")

    await session.commit()
    print("OK Phase 1 complete")


STATUSES_SEED = [
    {"name": "Abierto",     "slug": "open",        "color": "#3B82F6", "order": 1, "is_initial": True,  "is_final": False, "transitions": ["in_progress", "closed"]},
    {"name": "En Progreso", "slug": "in_progress",  "color": "#F59E0B", "order": 2, "is_initial": False, "is_final": False, "transitions": ["pending", "resolved", "open"]},
    {"name": "Pendiente",   "slug": "pending",      "color": "#8B5CF6", "order": 3, "is_initial": False, "is_final": False, "transitions": ["in_progress", "closed"]},
    {"name": "Resuelto",    "slug": "resolved",     "color": "#10B981", "order": 4, "is_initial": False, "is_final": False, "transitions": ["closed", "open"]},
    {"name": "Cerrado",     "slug": "closed",       "color": "#6B7280", "order": 5, "is_initial": False, "is_final": True,  "transitions": []},
]

PRIORITIES_SEED = [
    {"name": "Baja",    "level": 1, "color": "#6B7280", "is_default": False},
    {"name": "Media",   "level": 2, "color": "#3B82F6", "is_default": True},
    {"name": "Alta",    "level": 3, "color": "#F59E0B", "is_default": False},
    {"name": "Critica", "level": 4, "color": "#EF4444", "is_default": False},
]

ORIGINS_SEED = [
    {"name": "Email",    "code": "EMAIL"},
    {"name": "Telefono", "code": "PHONE"},
    {"name": "Chat",     "code": "CHAT"},
    {"name": "Portal",   "code": "PORTAL"},
]


async def seed_phase_2(session) -> None:
    """Seed case statuses, priorities, and origins."""
    from sqlalchemy import select

    status_count = 0
    for s in STATUSES_SEED:
        existing = await session.execute(
            select(CaseStatusModel).where(CaseStatusModel.slug == s["slug"], CaseStatusModel.tenant_id == None)
        )
        if existing.scalar_one_or_none():
            continue
        session.add(CaseStatusModel(
            id=str(uuid.uuid4()), tenant_id=None,
            name=s["name"], slug=s["slug"], color=s["color"],
            order=s["order"], is_initial=s["is_initial"], is_final=s["is_final"],
            allowed_transitions=s["transitions"],
        ))
        status_count += 1
    print(f"  + {status_count} estados de caso creados")

    priority_count = 0
    for p in PRIORITIES_SEED:
        existing = await session.execute(
            select(CasePriorityModel).where(CasePriorityModel.name == p["name"], CasePriorityModel.tenant_id == None)
        )
        if existing.scalar_one_or_none():
            continue
        session.add(CasePriorityModel(
            id=str(uuid.uuid4()), tenant_id=None,
            name=p["name"], level=p["level"], color=p["color"], is_default=p["is_default"],
        ))
        priority_count += 1
    print(f"  + {priority_count} prioridades creadas")

    origin_count = 0
    for o in ORIGINS_SEED:
        existing = await session.execute(
            select(OriginModel).where(OriginModel.code == o["code"], OriginModel.tenant_id == None)
        )
        if existing.scalar_one_or_none():
            continue
        session.add(OriginModel(id=str(uuid.uuid4()), tenant_id=None, name=o["name"], code=o["code"]))
        origin_count += 1
    print(f"  + {origin_count} origenes creados")

    await session.commit()
    print("OK Phase 2 complete")


SLA_POLICIES_SEED = [
    {"priority_name": "Baja",    "target_resolution_hours": 72},
    {"priority_name": "Media",   "target_resolution_hours": 24},
    {"priority_name": "Alta",    "target_resolution_hours": 8},
    {"priority_name": "Critica", "target_resolution_hours": 2},
]


async def seed_phase_3(session) -> None:
    """Seed SLA policies."""
    from sqlalchemy import select

    result = await session.execute(
        select(CasePriorityModel).where(CasePriorityModel.tenant_id == None)
    )
    priorities = {p.name: p.id for p in result.scalars().all()}

    count = 0
    for policy_data in SLA_POLICIES_SEED:
        priority_id = priorities.get(policy_data["priority_name"])
        if not priority_id:
            print(f"  WARNING Priority '{policy_data['priority_name']}' not found - skipping SLA policy")
            continue
        existing = await session.execute(
            select(SLAPolicyModel).where(
                SLAPolicyModel.priority_id == priority_id,
                SLAPolicyModel.tenant_id == None,
            )
        )
        if existing.scalar_one_or_none():
            continue
        session.add(SLAPolicyModel(
            id=str(uuid.uuid4()), tenant_id=None,
            priority_id=priority_id,
            target_resolution_hours=policy_data["target_resolution_hours"],
        ))
        count += 1

    print(f"  + {count} politicas SLA creadas")
    await session.commit()
    print("OK Phase 3 complete")


async def main() -> None:
    if not await verify_connection():
        sys.exit(1)

    print("Starting seed...")
    async with AsyncSessionLocal() as session:
        await seed_phase_1(session)
        await seed_phase_2(session)
        await seed_phase_3(session)
    print("OK Seed complete!")
    print("")
    print("  Login: admin@example.com / ChangeMe123!")


if __name__ == "__main__":
    asyncio.run(main())
