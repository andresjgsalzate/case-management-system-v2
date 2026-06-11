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
from backend.src.modules.tenants.infrastructure.models import TenantModel
from backend.src.modules.alert_reports.infrastructure.models import (
    AlertReportTemplateModel, AlertReportTemplateVersionModel,
)
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
from backend.src.modules.service_catalog.infrastructure.models import (
    ServiceCatalogCategoryModel, ServiceCatalogItemModel,
    ServiceCatalogFieldModel, CaseCustomValueModel,
)


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
    "attachments", "notifications", "automation", "search", "document_types",
    "service_catalog",
]

# Todas las acciones que existen en el sistema
ALL_ACTIONS = [
    "create", "read", "update", "delete", "manage", "export",
    "archive", "assign", "transition",
]

# ── SOC role bundles (ADR 0001 + docs/specs/orchestration-flows.md §6) ──
#
# Capacidades atómicas reales tomadas del inventario de PermissionChecker
# en los módulos SOC (forensic, security_taxonomies, integrations,
# alert_reports, approvals, triage usa cases:read/update).
#
# Jerarquía por composición: L2 = L1 + extra, Admin SOC = L2 + extra.
# NOTA: el gate de acción destructiva NO es un permiso `forensic:launch_
# destructive` (no existe) -- es `approvals:approve` (autorizar el
# ApprovalRequest) + el routing obligatorio por n8n
# (_enforce_destructive_governance). Por eso L1 (sin approvals:approve)
# no puede autorizar hunts destructivos; L2 sí.

_SOC_L1_PERMS = [
    # Casos + triage (los endpoints de triage usan cases:read/update)
    {"module": "cases",          "action": "read",            "scope": "all"},
    {"module": "cases",          "action": "update",          "scope": "all"},
    {"module": "cases",          "action": "transition",      "scope": "all"},
    {"module": "cases",          "action": "create:event",    "scope": "all"},
    {"module": "cases",          "action": "create:incident", "scope": "all"},
    {"module": "notes",          "action": "create",          "scope": "all"},
    {"module": "notes",          "action": "read",            "scope": "all"},
    {"module": "attachments",    "action": "create",          "scope": "all"},
    {"module": "attachments",    "action": "read",            "scope": "all"},
    {"module": "classification", "action": "read",            "scope": "all"},
    {"module": "classification", "action": "create",          "scope": "all"},
    {"module": "security_taxonomies", "action": "read",        "scope": "all"},
    # Lectura de tipos de documento KB (base, heredado por L2/Admin SOC)
    {"module": "document_types", "action": "read",            "scope": "all"},
    # Forense read-only (sin acciones destructivas)
    {"module": "forensic",       "action": "read",            "scope": "all"},
    {"module": "forensic",       "action": "launch_ro",       "scope": "all"},
    # Consultas outbound read-only de los playbooks n8n (Fase 2 + Fase 3).
    # Módulo/acción tomados literal de PermissionChecker en los routers:
    # enrichment/router.py -> ("enrichment","query"); wazuh_query/router.py
    # -> ("wazuh","query_syscheck"). No destructivas: reputación VT/OTX y
    # movimiento lateral por hash. En L1 para que L2/Admin las hereden.
    {"module": "enrichment",     "action": "query",           "scope": "all"},
    {"module": "wazuh",          "action": "query_syscheck",  "scope": "all"},
    # Reportes de alerta: ver + generar
    {"module": "alert_reports",  "action": "read",            "scope": "all"},
    {"module": "alert_reports",  "action": "generate",        "scope": "all"},
    # Integraciones: ver eventos entrantes (no gestionar)
    {"module": "integrations",   "action": "read_events",     "scope": "all"},
    # Cola de aprobaciones: VER pero NO aprobar (eso es L2)
    {"module": "approvals",      "action": "read",            "scope": "all"},
    {"module": "metrics",        "action": "read",            "scope": "all"},
    {"module": "sla",            "action": "read",            "scope": "all"},
    {"module": "notifications",  "action": "read",            "scope": "own"},
]

# L2 / Forense: autoriza acciones destructivas + gestiona reportes
_SOC_L2_EXTRA = [
    {"module": "approvals",      "action": "approve",         "scope": "all"},  # ← gate destructivo
    {"module": "forensic",       "action": "cancel_own",      "scope": "all"},
    {"module": "integrations",   "action": "read",            "scope": "all"},
    {"module": "integrations",   "action": "replay_events",   "scope": "all"},
    {"module": "alert_reports",  "action": "manage_templates","scope": "all"},
    {"module": "alert_reports",  "action": "set_default",     "scope": "all"},
    {"module": "alert_reports",  "action": "view_versions",   "scope": "all"},
    {"module": "alert_reports",  "action": "delete",          "scope": "all"},
    {"module": "security_taxonomies", "action": "read_audit_log", "scope": "all"},
    {"module": "n8n_editor",     "action": "access",          "scope": "all"},
]
_SOC_L2_PERMS = _SOC_L1_PERMS + _SOC_L2_EXTRA

# Admin SOC: gobernanza de taxonomías, integraciones, catálogos
_SOC_ADMIN_EXTRA = [
    {"module": "security_taxonomies", "action": "create",        "scope": "all"},
    {"module": "security_taxonomies", "action": "update",        "scope": "all"},
    {"module": "security_taxonomies", "action": "delete",        "scope": "all"},
    {"module": "security_taxonomies", "action": "manage_global", "scope": "all"},
    {"module": "integrations",        "action": "manage",        "scope": "all"},
    {"module": "forensic",            "action": "sync_catalog",  "scope": "all"},
    {"module": "forensic",            "action": "manage_featured","scope": "all"},
]
_SOC_ADMIN_PERMS = _SOC_L2_PERMS + _SOC_ADMIN_EXTRA

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
            {"module": "document_types","action": "read",      "scope": "all"},
        ],
    },
    {
        "name": "Reporter",
        "description": "Usuario que reporta y hace seguimiento de sus propios casos",
        "permissions": [
            {"module": "cases",          "action": "create",     "scope": "own"},
            {"module": "cases",          "action": "read",       "scope": "own"},
            {"module": "cases",          "action": "transition", "scope": "own"},
            {"module": "notifications",  "action": "read",       "scope": "own"},
            {"module": "document_types", "action": "read",       "scope": "all"},
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
            {"module": "document_types", "action": "read",      "scope": "all"},
        ],
    },
    # ── SOC roles (ADR 0001) — capability bundles, tiered by `level` ──
    {
        "name": "SOC Analyst L1",
        "description": "Analista SOC N1: triage, lectura forense, hunts read-only. NO autoriza acciones destructivas.",
        "level": 1,
        "permissions": _SOC_L1_PERMS,
    },
    {
        "name": "SOC Analyst L2",
        "description": "Analista SOC N2 / forense: aprueba acciones destructivas, gestiona reportes de alerta.",
        "level": 2,
        "permissions": _SOC_L2_PERMS,
    },
    {
        "name": "SOC Admin",
        "description": "Administrador SOC: gobernanza de taxonomías, integraciones y catálogos.",
        "level": 3,
        "permissions": _SOC_ADMIN_PERMS,
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
        # Sub-spec 01 § 3.6 granular case creation permissions
        {"module": "cases",          "action": "create:request",            "scope": "all"},
        {"module": "cases",          "action": "create:incident",           "scope": "all"},
        {"module": "cases",          "action": "create:event",              "scope": "all"},
        {"module": "cases",          "action": "promote:event_to_incident", "scope": "all"},
    ],
    "Reporter": [
        # Sub-spec 01 § 3.6 granular case creation permissions
        {"module": "cases",          "action": "create:request", "scope": "own"},
    ],
    # SOC roles: re-listing the full bundle here means re-running seed
    # repairs any capability added to the bundle constants later (only
    # missing perms are inserted; existing ones are left untouched).
    "SOC Analyst L1": _SOC_L1_PERMS,
    "SOC Analyst L2": _SOC_L2_PERMS,
    "SOC Admin": _SOC_ADMIN_PERMS,
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
        # Sub-spec 01 § 3.6 granular case creation permissions
        {"module": "cases",          "action": "create:request", "scope": "own"},
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
            level=role_data.get("level", 1),
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


CANONICAL_STATUSES = [
    # (slug, name, color, order, is_initial, is_final, pauses_sla, applies_to_case_types, allowed_transitions_slugs)
    ("new",            "Nuevo",                "#3b82f6", 10, True,  False, False, ["request", "incident"],           ["in_progress", "on_hold", "resolved", "triage"]),
    ("logged",         "Registrado",           "#94a3b8", 11, True,  False, False, ["event"],                         ["discarded", "resolved"]),
    ("pending_triage", "En triage automático", "#f59e0b", 12, False, False, False, ["event"],                         ["logged", "discarded"]),
    ("triage",         "En triage manual",     "#f59e0b", 20, False, False, False, ["incident"],                      ["in_response", "resolved"]),
    ("in_progress",    "En progreso",          "#3b82f6", 30, False, False, False, ["request"],                       ["on_hold", "resolved"]),
    ("in_response",    "En respuesta",         "#f97316", 31, False, False, False, ["incident"],                      ["contained", "resolved", "on_hold"]),
    ("contained",      "Contenido",            "#a855f7", 32, False, False, False, ["incident"],                      ["resolved"]),
    ("on_hold",        "En espera",            "#9ca3af", 40, False, False, True,  ["request", "incident"],           ["in_progress", "triage", "in_response", "resolved"]),
    ("resolved",       "Resuelto",             "#10b981", 50, False, False, False, ["request", "incident", "event"],  ["closed", "in_progress", "in_response"]),
    ("discarded",      "Descartado",           "#64748b", 51, False, True,  False, ["event"],                         []),
    ("closed",         "Cerrado",              "#475569", 60, False, True,  False, ["request", "incident", "event"],  []),
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


async def seed_case_statuses(session, tenant_id) -> None:
    """Idempotent seed: insert each canonical status if missing; update on existing rows.

    Two-pass logic: first inserts/updates statuses (without transitions), then resolves
    allowed_transitions slugs → status IDs. This avoids FK-like dependency between rows
    being inserted in same batch (a status can reference another that wasn't created yet).
    """
    from sqlalchemy import select

    # PASS 1: insert or update statuses with core fields + applies_to_case_types
    for slug, name, color, order, is_initial, is_final, pauses_sla, applies_to, _ in CANONICAL_STATUSES:
        result = await session.execute(
            select(CaseStatusModel).where(
                CaseStatusModel.slug == slug,
                CaseStatusModel.tenant_id == tenant_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = CaseStatusModel(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                slug=slug,
                name=name,
                color=color,
                order=order,
                is_initial=is_initial,
                is_final=is_final,
                pauses_sla=pauses_sla,
                applies_to_case_types=applies_to,
                allowed_transitions=[],
            )
            session.add(row)
        else:
            row.name = name
            row.color = color
            row.order = order
            row.is_initial = is_initial
            row.is_final = is_final
            row.pauses_sla = pauses_sla
            row.applies_to_case_types = applies_to

    await session.flush()

    # PASS 2: set allowed_transitions as slug lists (NOT IDs).
    # Existing code (case_statuses.use_cases.validate_transition + router DTO)
    # treats allowed_transitions as list[str] of target slugs. Keeping slugs
    # also matches the existing seed/migration patterns (e.g., migration
    # 067bf148971a updates allowed_transitions with slug strings via raw SQL).
    result = await session.execute(
        select(CaseStatusModel).where(CaseStatusModel.tenant_id == tenant_id)
    )
    all_rows = result.scalars().all()
    valid_slugs = {r.slug for r in all_rows}

    for slug, _, _, _, _, _, _, _, transitions_slugs in CANONICAL_STATUSES:
        row = next((r for r in all_rows if r.slug == slug), None)
        if row is None:
            continue
        row.allowed_transitions = [
            t_slug for t_slug in transitions_slugs if t_slug in valid_slugs
        ]

    await session.commit()
    print(f"  + Seeded {len(CANONICAL_STATUSES)} case statuses for tenant {tenant_id}")


async def seed_case_number_ranges(session, tenant_id) -> None:
    """Ensure tenant has 3 active number ranges: REQ, INC, EVT. Idempotent.

    Per sub-spec 01 § 3.3:
    - REQ 1-200000  (high-volume helpdesk requests)
    - INC 1-100000  (security incidents, rarer)
    - EVT 1-1000000 (security events, noisiest from Wazuh)
    """
    from sqlalchemy import select

    # (case_type, prefix, range_start, range_end)
    canonical_ranges = [
        ("request",  "REQ", 1,  200000),
        ("incident", "INC", 1,  100000),
        ("event",    "EVT", 1, 1000000),
    ]
    inserted = 0
    for case_type, prefix, start, end in canonical_ranges:
        existing = await session.execute(
            select(CaseNumberRangeModel).where(
                CaseNumberRangeModel.tenant_id == tenant_id,
                CaseNumberRangeModel.case_type == case_type,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue  # already exists for this type, skip
        row = CaseNumberRangeModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            case_type=case_type,
            prefix=prefix,
            range_start=start,
            range_end=end,
            current_number=start - 1,
        )
        session.add(row)
        inserted += 1
    await session.commit()
    print(f"  + Ensured 3 number ranges for tenant {tenant_id} ({inserted} new)")


async def seed_phase_2(session) -> None:
    """Seed case statuses, priorities, origins, and number ranges."""
    from sqlalchemy import select

    await seed_case_statuses(session, tenant_id=None)
    await seed_case_number_ranges(session, tenant_id=None)

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


# ── Reference data: prioritization engine (sub-spec 03 §4) ───────────────
# Exact values transcribed from docs/superpowers/specs/
# 2026-05-10-prioritization-engine-design.md §4.1-4.4.
_PRIO_CRITERIA = [
    # (code, name, description, data_source, source_field_key, strategy, default)
    ("severity", "Severidad de la alerta",
     "Severidad técnica reportada por la fuente de detección",
     "taxonomy_field", "default_severity_value", "use_default", 3),
    ("impact", "Impacto potencial",
     "Impacto estimado en el negocio si la amenaza se materializa",
     "case_custom_value", "impact", "use_default", 3),
    ("asset_criticality", "Criticidad del activo afectado",
     "Importancia del activo según el inventario de aplicaciones",
     "asset_field", "criticality", "skip", None),
    ("data_sensitivity", "Sensibilidad de la información (TLP)",
     "Nivel TLP de la información involucrada",
     "taxonomy_field", "tlp_default", "use_default", 3),
    ("user_visibility", "Cantidad de usuarios afectados",
     "Número estimado de usuarios impactados",
     "case_custom_value", "affected_users_estimate", "skip", None),
    ("repetition_count", "Frecuencia (repetición)",
     "Cuántas veces se ha visto un evento similar recientemente",
     "derived", "repetition_count_handler", "use_default", 1),
]

_PRIO_SCALES = [
    ("Mínimo", 1, "#94a3b8"), ("Bajo", 2, "#22c55e"), ("Medio", 3, "#f59e0b"),
    ("Alto", 4, "#f97316"), ("Crítico", 5, "#ef4444"),
]

_PRIO_FORMULAS = [
    {"logical_key": "soc-default", "name": "SOC Default Formula 2026",
     "description": "Fórmula balanceada para operación SOC general",
     "weights": {"severity": "0.50", "impact": "0.30", "asset_criticality": "0.20"},
     "thresholds": [("4.50", "5.00", "critical"), ("3.50", "4.49", "high"),
                    ("2.50", "3.49", "medium"), ("0.00", "2.49", "low")]},
    {"logical_key": "compliance-focused", "name": "Compliance-Focused Formula",
     "description": "Énfasis en sensibilidad de información (PCI, GDPR, etc.)",
     "weights": {"data_sensitivity": "0.40", "severity": "0.30", "impact": "0.30"},
     "thresholds": [("4.00", "5.00", "critical"), ("3.00", "3.99", "high"),
                    ("2.00", "2.99", "medium"), ("0.00", "1.99", "low")]},
    {"logical_key": "user-impact-focused", "name": "User Impact Formula",
     "description": "Énfasis en cantidad de usuarios afectados",
     "weights": {"user_visibility": "0.40", "severity": "0.30", "impact": "0.30"},
     "thresholds": [("4.50", "5.00", "critical"), ("3.50", "4.49", "high"),
                    ("2.50", "3.49", "medium"), ("0.00", "2.49", "low")]},
]

# case_priorities has no slug column; map the spec's threshold slugs to the
# seeded priority names (level 1=Baja .. 4=Critica).
_PRIO_SLUG_TO_PRIORITY = {
    "critical": "Critica", "high": "Alta", "medium": "Media", "low": "Baja",
}

_PRIO_PERMISSIONS = [
    "read", "manage_criteria", "manage_formulas",
    "manage_global", "recalculate", "read_calculations",
]


async def seed_prioritization(session) -> None:
    """Seed prioritization reference data: 6 criteria + 5 scales each + 3
    formulas (weights + thresholds) + 6 permissions. Idempotent by natural key."""
    from decimal import Decimal
    from sqlalchemy import select
    from backend.src.modules.prioritization.infrastructure.models import (
        PrioritizationCriterionModel, PrioritizationScaleModel,
        PrioritizationFormulaModel, PrioritizationFormulaCriterionModel,
        PrioritizationThresholdModel,
    )

    crit_ids: dict[str, str] = {}
    for code, name, desc, ds, sfk, strat, dflt in _PRIO_CRITERIA:
        existing = (await session.execute(
            select(PrioritizationCriterionModel).where(
                PrioritizationCriterionModel.tenant_id.is_(None),
                PrioritizationCriterionModel.code == code,
            )
        )).scalar_one_or_none()
        if existing:
            crit_ids[code] = existing.id
            continue
        cid = str(uuid.uuid4())
        crit_ids[code] = cid
        session.add(PrioritizationCriterionModel(
            id=cid, tenant_id=None, code=code, name=name, description=desc,
            data_source=ds, source_field_key=sfk, missing_data_strategy=strat,
            default_value=dflt,
        ))
        for label, value, color in _PRIO_SCALES:
            session.add(PrioritizationScaleModel(
                id=str(uuid.uuid4()), criterion_id=cid,
                label=label, numeric_value=value, color=color, sort_order=value,
            ))
    await session.commit()

    prio_by_name = {
        p.name: p.id for p in (await session.execute(
            select(CasePriorityModel).where(CasePriorityModel.tenant_id.is_(None))
        )).scalars().all()
    }
    creator = (await session.execute(select(UserModel.id).limit(1))).scalar_one_or_none()
    if not creator:
        print("  WARNING no user for formula.created_by — skipping formulas")
        return

    for f in _PRIO_FORMULAS:
        existing = (await session.execute(
            select(PrioritizationFormulaModel).where(
                PrioritizationFormulaModel.tenant_id.is_(None),
                PrioritizationFormulaModel.logical_key == f["logical_key"],
            )
        )).scalar_one_or_none()
        if existing:
            continue
        fid = str(uuid.uuid4())
        session.add(PrioritizationFormulaModel(
            id=fid, tenant_id=None, logical_key=f["logical_key"], version=1,
            name=f["name"], description=f["description"], is_active=True,
            created_by=creator,
        ))
        # Flush the parent first: the self-referential FK (superseded_by_id)
        # breaks SQLAlchemy's insert ordering, so children would otherwise hit
        # the formula FK before the row exists.
        await session.flush()
        for i, (code, w) in enumerate(f["weights"].items()):
            session.add(PrioritizationFormulaCriterionModel(
                id=str(uuid.uuid4()), formula_id=fid, criterion_id=crit_ids[code],
                weight=Decimal(w), sort_order=i,
            ))
        for i, (mn, mx, slug) in enumerate(f["thresholds"]):
            pid = prio_by_name.get(_PRIO_SLUG_TO_PRIORITY[slug])
            if not pid:
                print(f"  WARNING priority for slug '{slug}' missing — skipping threshold")
                continue
            session.add(PrioritizationThresholdModel(
                id=str(uuid.uuid4()), formula_id=fid,
                min_value=Decimal(mn), max_value=Decimal(mx),
                priority_id=pid, sort_order=i,
            ))
    await session.commit()

    # Permissions: the test only requires the 6 actions to exist under module
    # 'prioritization'; attach them to Super Admin.
    sa = (await session.execute(
        select(RoleModel).where(RoleModel.name == "Super Admin")
    )).scalar_one_or_none()
    if sa:
        existing_actions = {
            p.action for p in (await session.execute(
                select(PermissionModel).where(
                    PermissionModel.role_id == sa.id,
                    PermissionModel.module == "prioritization",
                )
            )).scalars().all()
        }
        for action in _PRIO_PERMISSIONS:
            if action not in existing_actions:
                session.add(PermissionModel(
                    id=str(uuid.uuid4()), role_id=sa.id,
                    module="prioritization", action=action, scope="all",
                ))
        await session.commit()
    print("OK prioritization seeded")


# ── Reference data: 17 global SOC teams (security-taxonomies spec §4.1) ───
_SOC_TEAMS = [
    ("Incidentes - SOC", "operational", False),
    ("Soporte IT", "operational", False),
    ("Customer Success", "operational", True),
    ("Infraestructura", "technical_support", False),
    ("Bases de datos", "technical_support", False),
    ("Aplicaciones", "technical_support", False),
    ("Adm. Antivirus", "technical_support", False),
    ("Adm. Correo", "technical_support", False),
    ("Net&Sec", "technical_support", False),
    ("Ethical Hacker", "technical_support", False),
    ("Segu Info. - Risk", "governance", False),
    ("Recursos Humanos", "governance", True),
    ("Datos Personales", "governance", True),
    ("Legal", "legal", True),
    ("Director de Producto", "executive", True),
    ("Director Arquitectura", "executive", True),
    ("Alta Dirección", "executive", True),
]


async def seed_soc_teams(session) -> None:
    """Seed the 17 global SOC teams. Idempotent by name; keeps attrs in sync."""
    from sqlalchemy import select

    count = 0
    for name, category, notif_only in _SOC_TEAMS:
        existing = (await session.execute(
            select(TeamModel).where(
                TeamModel.tenant_id.is_(None), TeamModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            existing.team_category = category
            existing.is_notification_only = notif_only
            continue
        session.add(TeamModel(
            id=str(uuid.uuid4()), tenant_id=None, name=name,
            team_category=category, is_notification_only=notif_only,
        ))
        count += 1
    await session.commit()
    print(f"  + {count} SOC teams seeded")


# ── Reference data: security-taxonomies extras (sub-spec 02) ─────────────
# Exact security_taxonomies permission matrix per base role (Task 4).
_SEC_TAX_PERM_MATRIX = {
    "Super Admin": {"read", "create", "update", "delete",
                    "manage_global", "read_audit_log", "export", "import"},
    "Admin":       {"read", "create", "update", "delete",
                    "read_audit_log", "export", "import"},
    "Manager":     {"read", "create", "update", "read_audit_log", "export"},
    "Agent":       {"read", "read_audit_log"},
    "Reporter":    {"read"},
}


async def seed_security_taxonomy_extras(session) -> None:
    """Seed the RANSOM-LOCKBIT fixture taxonomy (child of RANSOMWARE, Task 6)
    plus the security_taxonomies permission matrix on the 5 base roles."""
    from sqlalchemy import select
    from backend.src.modules.security_taxonomies.infrastructure.models import (
        SecurityTaxonomyModel,
    )

    # Task 6 fixtures: (code, name, parent_code, tlp_default). RANSOM-LOCKBIT's
    # parent is asserted == RANSOMWARE; PHISH-MAIL just needs to exist global.
    _tax_fixtures = [
        ("RANSOM-LOCKBIT", "Ransomware LockBit", "RANSOMWARE", "red"),
        ("PHISH-MAIL", "Phishing por correo", "PHISHING-SPEAR-PHISHING", "amber"),
    ]
    creator = (await session.execute(select(UserModel.id).limit(1))).scalar_one_or_none()
    for code, name, parent_code, tlp in _tax_fixtures:
        exists = (await session.execute(
            select(SecurityTaxonomyModel).where(
                SecurityTaxonomyModel.tuic_code == code,
                SecurityTaxonomyModel.tenant_id.is_(None),
            )
        )).scalar_one_or_none()
        if exists:
            continue
        parent = (await session.execute(
            select(SecurityTaxonomyModel).where(
                SecurityTaxonomyModel.tuic_code == parent_code,
                SecurityTaxonomyModel.tenant_id.is_(None),
            )
        )).scalar_one_or_none()
        if not parent:
            print(f"  WARNING parent '{parent_code}' missing — skipping {code}")
            continue
        session.add(SecurityTaxonomyModel(
            id=str(uuid.uuid4()), tenant_id=None,
            tuic_code=code, name=name,
            description=f"Fixture global {code}",
            parent_id=parent.id,
            default_case_type="event", requires_ticket=False,
            triage_mode="auto", triage_timeout_seconds=300,
            tlp_default=tlp, mitre_techniques=[],
            is_active=True, created_by=creator,
        ))
        print(f"  + {code} taxonomy seeded")
    await session.commit()

    for role_name, actions in _SEC_TAX_PERM_MATRIX.items():
        role = (await session.execute(
            select(RoleModel).where(
                RoleModel.name == role_name, RoleModel.tenant_id.is_(None),
            )
        )).scalar_one_or_none()
        if not role:
            continue
        existing = {
            p.action for p in (await session.execute(
                select(PermissionModel).where(
                    PermissionModel.role_id == role.id,
                    PermissionModel.module == "security_taxonomies",
                )
            )).scalars().all()
        }
        for action in actions:
            if action not in existing:
                session.add(PermissionModel(
                    id=str(uuid.uuid4()), role_id=role.id,
                    module="security_taxonomies", action=action, scope="all",
                ))
    await session.commit()
    print("OK security_taxonomies extras seeded")


async def seed_default_soc_template(session) -> None:
    """Seed the global SOC standard alert-report template (master spec §7).

    Global (``tenant_id IS NULL``) default template ``soc_standard`` with a
    single immutable v1 covering the 8 sections operators expect. Idempotent:
    skips if the template already exists. The circular FK between template and
    version requires the two-step flush dance (see ``create_template``)."""
    from sqlalchemy import select
    from backend.src.modules.alert_reports.infrastructure.models import (
        AlertReportTemplateModel, AlertReportTemplateVersionModel,
    )

    exists = (await session.execute(
        select(AlertReportTemplateModel).where(
            AlertReportTemplateModel.code == "soc_standard",
            AlertReportTemplateModel.tenant_id.is_(None),
        )
    )).scalar_one_or_none()
    if exists:
        print("  ~ soc_standard template already seeded, skipping")
        return

    # Incident-flow order: what happened, how severe, classification, how the
    # attacker acted, techniques, evidence, chain-of-custody, what to do next.
    blocks = [
        {"type": "alert_metadata", "params": {}},
        {"type": "priority_calculation", "params": {}},
        {"type": "triage_analysis", "params": {}},
        {"type": "behavior_relation", "params": {}},
        {"type": "mitre_techniques", "params": {}},
        {"type": "evidence_grid", "params": {}},
        {"type": "forensic_artifacts_list", "params": {}},
        {"type": "recommendations", "params": {}},
    ]

    template = AlertReportTemplateModel(
        id=str(uuid.uuid4()), tenant_id=None,
        name="SOC Standard", code="soc_standard",
        description="Plantilla global estándar de reporte de alerta SOC.",
        is_default=True, is_active=True,
    )
    session.add(template)
    await session.flush()  # need template.id for the v1 row

    version = AlertReportTemplateVersionModel(
        id=str(uuid.uuid4()), template_id=template.id, version=1,
        name_snapshot="SOC Standard",
        header_config={}, footer_config={}, blocks=blocks,
        change_summary="Versión inicial (seed)",
    )
    session.add(version)
    await session.flush()  # need version.id for the back-pointer

    template.current_version_id = version.id
    template.current_version_number = 1
    await session.commit()
    print("  + soc_standard template seeded")


async def seed_reference_data(session) -> None:
    """Opt-in reference data the integration tests assert on (statuses,
    priorities, SLA, classification, prioritization, SOC teams,
    security-taxonomies extras, default alert-report template). Idempotent."""
    await seed_phase_2(session)
    await seed_phase_3(session)
    await seed_phase_4(session)
    await seed_prioritization(session)
    await seed_soc_teams(session)
    await seed_security_taxonomy_extras(session)
    await seed_default_soc_template(session)
    print("OK Reference data seeded")


async def main() -> None:
    """Minimal seed — only what's needed to bootstrap a fresh deploy.

    Scope (post 2026-05-19 refactor):
    - Ensures default roles exist (Super Admin, Admin, Manager, Reporter, Agent)
    - Repairs the permission set for those roles (keeps the permission catalog
      in sync with code-defined modules/actions)

    Explicitly NOT seeded — clients configure these themselves:
    - Case statuses / priorities / number ranges
    - SLA policies / holidays / work schedules
    - Classification criteria / rules / thresholds
    - Origins / applications / service catalog
    - Any operational data

    The skipped seed_phase_2 / seed_phase_3 / seed_phase_4 functions remain in
    this file for emergency restore or test fixtures. Call them explicitly if
    needed (``python -m scripts.seed --include-reference-data`` is the
    intended UX but not implemented here yet).
    """
    if not await verify_connection():
        sys.exit(1)

    include_ref = "--include-reference-data" in sys.argv
    mode = "with reference data" if include_ref else "bootstrap-only"
    print(f"Starting seed ({mode} mode)...")
    async with AsyncSessionLocal() as session:
        await repair_permissions(session)
        await seed_phase_1(session)
        if include_ref:
            await seed_reference_data(session)
    if include_ref:
        print("OK Seed complete (bootstrap + reference data).")
    else:
        print("OK Bootstrap seed complete. Reference data left for client config.")


if __name__ == "__main__":
    asyncio.run(main())
