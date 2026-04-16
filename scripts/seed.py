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
from backend.src.modules.cases.infrastructure.models import CaseNumberSequenceModel, CaseNumberRangeModel, CaseModel
from backend.src.modules.assignment.infrastructure.models import CaseAssignmentModel
from backend.src.modules.activity.infrastructure.models import ActivityEntryModel
from backend.src.modules.classification.infrastructure.models import (
    CaseClassificationModel, ClassificationRuleModel,
    ClassificationCriterionModel, ClassificationThresholdModel,
)
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


# Módulos exactamente como los usa el backend (PermissionChecker)
MODULES = [
    "cases", "users", "teams", "roles", "sla", "knowledge_base", "audit",
    "metrics", "dispositions", "todos", "notes", "time_entries", "classification",
    "attachments", "notifications", "automation", "search",
]

# Todas las acciones que existen en el sistema
ALL_ACTIONS = [
    "create", "read", "update", "delete", "manage", "export",
    "archive", "assign", "transition",
]

ROLES_SEED = [
    {
        "name": "Super Admin",
        "description": "Acceso total al sistema",
        "is_global": True,
        "permissions": [
            {"module": m, "action": a, "scope": "all"}
            for m in MODULES
            for a in ALL_ACTIONS
        ],
    },
    {
        "name": "Admin",
        "description": "Administrador del sistema",
        "permissions": [
            {"module": m, "action": a, "scope": "all"}
            for m in MODULES if m != "roles"
            for a in ALL_ACTIONS
        ],
    },
    {
        "name": "Manager",
        "description": "Manager de equipos",
        "permissions": [
            {"module": "cases",          "action": "read",      "scope": "all"},
            {"module": "cases",          "action": "update",    "scope": "all"},
            {"module": "cases",          "action": "assign",    "scope": "all"},
            {"module": "cases",          "action": "transition","scope": "all"},
            {"module": "cases",          "action": "export",    "scope": "all"},
            {"module": "cases",          "action": "archive",   "scope": "all"},
            {"module": "users",          "action": "read",      "scope": "all"},
            {"module": "metrics",        "action": "read",      "scope": "all"},
            {"module": "teams",          "action": "read",      "scope": "all"},
            {"module": "teams",          "action": "manage",    "scope": "all"},
            {"module": "audit",          "action": "read",      "scope": "all"},
            {"module": "knowledge_base", "action": "read",      "scope": "all"},
            {"module": "knowledge_base", "action": "create",    "scope": "all"},
            {"module": "knowledge_base", "action": "manage",    "scope": "all"},
            {"module": "dispositions",   "action": "read",      "scope": "all"},
            {"module": "dispositions",   "action": "manage",    "scope": "all"},
            {"module": "sla",            "action": "read",      "scope": "all"},
            {"module": "notes",          "action": "read",      "scope": "all"},
            {"module": "search",         "action": "read",      "scope": "all"},
            {"module": "classification", "action": "read",      "scope": "all"},
        ],
    },
    {
        "name": "Reporter",
        "description": "Usuario que reporta y hace seguimiento de sus propios casos",
        "permissions": [
            {"module": "cases",         "action": "create",     "scope": "own"},
            {"module": "cases",         "action": "read",       "scope": "own"},
            {"module": "cases",         "action": "transition", "scope": "own"},
            {"module": "notifications", "action": "read",       "scope": "own"},
        ],
    },
    {
        "name": "Agent",
        "description": "Agente de soporte",
        "permissions": [
            {"module": "cases",          "action": "create",    "scope": "own"},
            {"module": "cases",          "action": "read",      "scope": "team"},
            {"module": "cases",          "action": "update",    "scope": "own"},
            {"module": "cases",          "action": "transition","scope": "own"},
            {"module": "cases",          "action": "assign",    "scope": "own"},
            {"module": "users",          "action": "read",      "scope": "all"},
            {"module": "todos",          "action": "create",    "scope": "own"},
            {"module": "todos",          "action": "read",      "scope": "own"},
            {"module": "notes",          "action": "create",    "scope": "own"},
            {"module": "notes",          "action": "read",      "scope": "team"},
            {"module": "notes",          "action": "delete",    "scope": "own"},
            {"module": "time_entries",   "action": "create",    "scope": "own"},
            {"module": "time_entries",   "action": "read",      "scope": "own"},
            {"module": "knowledge_base", "action": "read",      "scope": "all"},
            {"module": "knowledge_base", "action": "create",    "scope": "all"},
            {"module": "notifications",  "action": "read",      "scope": "own"},
            {"module": "attachments",    "action": "create",    "scope": "own"},
            {"module": "attachments",    "action": "read",      "scope": "team"},
            {"module": "attachments",    "action": "delete",    "scope": "own"},
            {"module": "search",         "action": "read",      "scope": "all"},
            {"module": "classification", "action": "read",      "scope": "own"},
            {"module": "classification", "action": "create",    "scope": "own"},
            {"module": "dispositions",   "action": "read",      "scope": "all"},
            {"module": "dispositions",   "action": "create",    "scope": "own"},
            {"module": "cases",          "action": "archive",   "scope": "own"},
            {"module": "sla",            "action": "read",      "scope": "own"},
        ],
    },
]

# Correcciones de nombres de módulo: (nombre_viejo → nombre_correcto)
# Necesario para reparar datos existentes en BD que tienen nombres incorrectos
MODULE_RENAMES = {
    "knowledge": "knowledge_base",
    "time":      "time_entries",
}

# Permisos que deben existir en cada rol pero que pueden faltar
# (se insertan solo si no existen ya)
ROLE_PERMISSION_ADDITIONS = {
    "Super Admin": [
        {"module": m, "action": a, "scope": "all"}
        for m in MODULES
        for a in ALL_ACTIONS
    ],
    "Admin": [
        {"module": m, "action": a, "scope": "all"}
        for m in MODULES if m != "roles"
        for a in ALL_ACTIONS
    ],
    "Manager": [
        {"module": "cases",          "action": "update",     "scope": "all"},
        {"module": "cases",          "action": "transition", "scope": "all"},
        {"module": "users",          "action": "read",       "scope": "all"},
        {"module": "knowledge_base", "action": "create",     "scope": "all"},
        {"module": "knowledge_base", "action": "manage",     "scope": "all"},
        {"module": "dispositions",   "action": "manage",     "scope": "all"},
        {"module": "search",         "action": "read",       "scope": "all"},
    ],
    "Agent": [
        {"module": "cases",          "action": "assign",  "scope": "own"},
        {"module": "users",          "action": "read",    "scope": "all"},
        {"module": "teams",          "action": "read",    "scope": "all"},
        {"module": "time_entries",   "action": "create",  "scope": "own"},
        {"module": "time_entries",   "action": "read",    "scope": "own"},
        {"module": "knowledge_base", "action": "read",    "scope": "all"},
        {"module": "knowledge_base", "action": "create",  "scope": "all"},
        {"module": "notes",          "action": "delete",  "scope": "own"},
        {"module": "attachments",    "action": "delete",  "scope": "own"},
        {"module": "search",         "action": "read",    "scope": "all"},
        {"module": "classification", "action": "read",    "scope": "own"},
        {"module": "classification", "action": "create",  "scope": "own"},
        {"module": "dispositions",   "action": "read",    "scope": "all"},
        {"module": "dispositions",   "action": "create",  "scope": "own"},
        {"module": "cases",          "action": "archive", "scope": "own"},
        {"module": "sla",            "action": "read",    "scope": "own"},
    ],
}


async def repair_permissions(session) -> None:
    """
    Repair existing permission data in the DB:
    1. Rename incorrect module names (knowledge→knowledge_base, time→time_entries).
    2. Insert missing permissions for existing roles.
    """
    from sqlalchemy import select, update

    print("\n--- Repairing permissions ---")

    # 1. Fix module name renames
    for old_name, new_name in MODULE_RENAMES.items():
        result = await session.execute(
            select(PermissionModel).where(PermissionModel.module == old_name)
        )
        old_rows = result.scalars().all()
        if not old_rows:
            print(f"  Module '{old_name}' not found in DB (already correct or not seeded yet)")
            continue

        renamed = 0
        deleted = 0
        for p in old_rows:
            # Check if the correctly-named version already exists for this role+action
            conflict = await session.execute(
                select(PermissionModel).where(
                    PermissionModel.role_id == p.role_id,
                    PermissionModel.module == new_name,
                    PermissionModel.action == p.action,
                )
            )
            if conflict.scalar_one_or_none():
                # Duplicate: remove the old-name entry
                await session.delete(p)
                deleted += 1
            else:
                # Safe to rename
                p.module = new_name
                renamed += 1

        await session.flush()
        print(f"  Module '{old_name}' -> '{new_name}': {renamed} renamed, {deleted} duplicates removed")

    # 2. Add missing permissions to existing roles
    for role_name, perms_to_add in ROLE_PERMISSION_ADDITIONS.items():
        result = await session.execute(
            select(RoleModel).where(RoleModel.name == role_name, RoleModel.tenant_id == None)
        )
        role = result.scalar_one_or_none()
        if not role:
            print(f"  Role '{role_name}' not found - skipping additions")
            continue

        # Get existing permissions for this role
        existing_result = await session.execute(
            select(PermissionModel).where(PermissionModel.role_id == role.id)
        )
        existing = {(p.module, p.action) for p in existing_result.scalars().all()}

        added = 0
        for perm in perms_to_add:
            key = (perm["module"], perm["action"])
            if key not in existing:
                session.add(PermissionModel(
                    id=str(uuid.uuid4()),
                    role_id=role.id,
                    module=perm["module"],
                    action=perm["action"],
                    scope=perm["scope"],
                ))
                existing.add(key)
                added += 1

        if added:
            print(f"  + Added {added} missing permissions to '{role_name}'")
        else:
            print(f"  '{role_name}' already has all required permissions")

    await session.commit()
    print("OK Permissions repaired")


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
            is_global=role_data.get("is_global", False),
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

    await session.commit()
    print("OK Phase 1 complete")


STATUSES_SEED = [
    {"name": "Abierto",     "slug": "open",        "color": "#3B82F6", "order": 1, "is_initial": True,  "is_final": False, "pauses_sla": False, "transitions": ["in_progress"]},
    {"name": "En Progreso", "slug": "in_progress",  "color": "#F59E0B", "order": 2, "is_initial": False, "is_final": False, "pauses_sla": False, "transitions": ["pending", "resolved", "open"]},
    {"name": "Pendiente",   "slug": "pending",      "color": "#8B5CF6", "order": 3, "is_initial": False, "is_final": False, "pauses_sla": True,  "transitions": ["in_progress", "open"]},
    {"name": "Resuelto",    "slug": "resolved",     "color": "#10B981", "order": 4, "is_initial": False, "is_final": False, "pauses_sla": True,  "transitions": ["closed", "open"]},
    {"name": "Cerrado",     "slug": "closed",       "color": "#6B7280", "order": 5, "is_initial": False, "is_final": True,  "pauses_sla": False, "transitions": []},
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
        result = await session.execute(
            select(CaseStatusModel).where(CaseStatusModel.slug == s["slug"], CaseStatusModel.tenant_id == None)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.allowed_transitions = s["transitions"]
            existing.pauses_sla = s["pauses_sla"]
        else:
            session.add(CaseStatusModel(
                id=str(uuid.uuid4()), tenant_id=None,
                name=s["name"], slug=s["slug"], color=s["color"],
                order=s["order"], is_initial=s["is_initial"], is_final=s["is_final"],
                pauses_sla=s["pauses_sla"],
                allowed_transitions=s["transitions"],
            ))
            status_count += 1
    print(f"  + {status_count} estados de caso creados (transiciones actualizadas)")

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


DEFAULT_CRITERIA = [
    {
        "order": 1,
        "name": "Historial del Caso",
        "score1_description": "Si el error es conocido y ha sido solucionado previamente, es probable que sea fácil de manejar.",
        "score2_description": "Si el error es recurrente pero no ha sido solucionado previamente, podría requerir más análisis.",
        "score3_description": "Si el error es desconocido y no ha sido solucionado previamente.",
    },
    {
        "order": 2,
        "name": "Conocimiento del Módulo de la Aplicación",
        "score1_description": "Si se conoce el módulo de la aplicación y la función puntual del fallo.",
        "score2_description": "Si se conoce el módulo, pero no la función puntual del fallo y se requiere capacitación.",
        "score3_description": "Si se desconoce el módulo, la función puntual del fallo y se requiere capacitación.",
    },
    {
        "order": 3,
        "name": "Manipulación de Datos",
        "score1_description": "Si la manipulación de datos es mínima o no es necesaria.",
        "score2_description": "Si implica manipulación intensiva de datos, donde no sea necesario la replicación de la lógica de la aplicación (como cambio de estados, inserción o cambio de datos).",
        "score3_description": "Si implica una manipulación extremadamente compleja de datos que requiera la replicación de la lógica de la aplicación.",
    },
    {
        "order": 4,
        "name": "Claridad en la Descripción del Problema",
        "score1_description": "Una descripción clara y precisa facilita la resolución del problema.",
        "score2_description": "Si la descripción del problema es ambigua o poco clara, puede requerir más tiempo para entenderlo.",
        "score3_description": "Si la descripción del problema es muy confusa o inexacta, puede llevar mucho tiempo entender y abordar el problema.",
    },
    {
        "order": 5,
        "name": "Causa del Fallo",
        "score1_description": "Si es un error operativo que puede solucionarse fácilmente.",
        "score2_description": "Si es una falla de software puntual que requiere pruebas con el fin de replicar el fallo.",
        "score3_description": "Si la falla de software es compleja y requiere pruebas adicionales con el fin de encontrar dónde se genera el fallo.",
    },
]


async def seed_phase_4(session) -> None:
    """Seed classification criteria and thresholds."""
    from sqlalchemy import select

    # Seed criteria (tenant_id=None = global/system)
    existing = await session.execute(
        select(ClassificationCriterionModel).where(ClassificationCriterionModel.tenant_id == None)
    )
    if existing.scalars().first():
        print("  ~ Classification criteria already seeded, skipping")
    else:
        for data in DEFAULT_CRITERIA:
            session.add(ClassificationCriterionModel(
                id=str(uuid.uuid4()),
                tenant_id=None,
                **data,
            ))
        print(f"  + {len(DEFAULT_CRITERIA)} criterios de clasificación creados")

    # Seed thresholds
    existing_thresh = await session.execute(
        select(ClassificationThresholdModel).where(ClassificationThresholdModel.tenant_id == None)
    )
    if not existing_thresh.scalar_one_or_none():
        session.add(ClassificationThresholdModel(
            id=str(uuid.uuid4()),
            tenant_id=None,
            low_max=6,
            medium_max=11,
        ))
        print("  + Umbrales de clasificación creados (BAJA: 1-6, MEDIA: 7-11, ALTA: 12-15)")

    await session.commit()
    print("OK Phase 4 complete")


async def main() -> None:
    if not await verify_connection():
        sys.exit(1)

    print("Starting seed...")
    async with AsyncSessionLocal() as session:
        await repair_permissions(session)   # siempre primero: repara datos existentes
        await seed_phase_1(session)
        await seed_phase_2(session)
        await seed_phase_3(session)
        await seed_phase_4(session)
    print("OK Seed complete!")


if __name__ == "__main__":
    asyncio.run(main())
