"""
Database seed script.
Run from the project root: python scripts/seed.py

Each phase adds its own seed data in the corresponding section.
Requires DATABASE_URL and SECRET_KEY in environment or backend/.env
"""
import asyncio
import os
import sys

# Add backend/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
except ImportError:
    pass  # python-dotenv optional

import uuid

from src.core.config import get_settings
from src.core.database import AsyncSessionLocal
from src.core.security import hash_password


async def verify_connection() -> bool:
    """Verify PostgreSQL connectivity before seeding."""
    from sqlalchemy import text
    settings = get_settings()
    # Hide credentials in output
    db_display = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "localhost"
    print(f"Connecting to: {db_display}")
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
        print("✓ Database connection OK")
        return True
    except Exception as exc:
        print(f"✗ Database connection failed: {exc}")
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
    """Seed users, roles, teams, and permissions."""
    from sqlalchemy import select
    from src.modules.roles.infrastructure.models import RoleModel, PermissionModel
    from src.modules.users.infrastructure.models import UserModel

    role_map: dict[str, str] = {}

    for role_data in ROLES_SEED:
        # Check if role already exists (idempotent)
        existing = await session.execute(
            select(RoleModel).where(
                RoleModel.name == role_data["name"],
                RoleModel.tenant_id == None,
            )
        )
        existing_role = existing.scalar_one_or_none()
        if existing_role:
            role_map[role_data["name"]] = existing_role.id
            print(f"  Role '{role_data['name']}' already exists — skipping")
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
        print(f"  ✓ Role '{role_data['name']}' created with {len(role_data['permissions'])} permissions")

    # Create admin user
    admin_email = "admin@cms.local"
    existing_admin = await session.execute(
        select(UserModel).where(UserModel.email == admin_email)
    )
    if existing_admin.scalar_one_or_none():
        print("  Admin user already exists — skipping")
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
        print(f"  ✓ Admin user created: {admin_email} (password: ChangeMe123!)")

    await session.commit()
    print("✓ Phase 1 seed complete")


# ─── Phase 2: Cases ──────────────────────────────────────────────────────────
async def seed_phase_2(session) -> None:
    """Seed sample cases. Populated in Phase 2."""
    pass


# ─── Phase 3: SLA Policies ───────────────────────────────────────────────────
async def seed_phase_3(session) -> None:
    """Seed SLA policies. Populated in Phase 3."""
    pass


async def main() -> None:
    if not await verify_connection():
        sys.exit(1)

    print("Starting seed...")
    async with AsyncSessionLocal() as session:
        await seed_phase_1(session)
        await seed_phase_2(session)
        await seed_phase_3(session)
    print("✓ Seed complete")


if __name__ == "__main__":
    asyncio.run(main())
