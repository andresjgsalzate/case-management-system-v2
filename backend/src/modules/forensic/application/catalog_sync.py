"""Daily Velociraptor catalog sync into ``forensic_artifacts``.

Sync strategy:
- Iterate every tenant with ``velo_org_id`` set.
- For each tenant, list artifacts from Velociraptor (scoped to the org).
- Upsert by ``(tenant_id, name)``: insert new ones, refresh metadata on
  existing ones, mark missing ones inactive (never delete — preserves
  FK history from ``forensic_hunts.artifact_id``).
- Admin-managed flags (``is_featured``, ``is_destructive``,
  ``requires_evidence_handling``, ``category``, ``default_timeout_seconds``)
  are NEVER overwritten on re-sync. They are seeded once via heuristics
  on initial insert; admins can override afterwards without losing the
  override on the next nightly sync.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.forensic.infrastructure.models import (
    ForensicArtifactModel,
)
from backend.src.modules.forensic.infrastructure.velo_client import (
    get_velo_client,
)
from backend.src.modules.tenants.infrastructure.models import TenantModel

logger = logging.getLogger(__name__)


DESTRUCTIVE_KEYWORDS = (
    "Quarantine", "Kill", "Remove", "Delete", "Wipe",
    "Disable", "Block", "Disconnect",
)
EVIDENCE_KEYWORDS = (
    "Memory.Acquire", "Disk.Image", "Network.PacketCapture",
    "Forensics.Timeline", "Registry.Dump",
)


def detect_destructive(name: str) -> bool:
    return any(kw in name for kw in DESTRUCTIVE_KEYWORDS)


def detect_evidence(name: str) -> bool:
    return any(kw in name for kw in EVIDENCE_KEYWORDS)


def infer_category(name: str) -> str | None:
    if "Detection" in name or "Yara" in name:
        return "detection"
    if "Memory" in name or "Disk" in name or "Forensics" in name:
        return "collection"
    if "Quarantine" in name or "Kill" in name or "Remove" in name:
        return "remediation"
    if "Process" in name or "Network" in name:
        return "live_response"
    if "Persistence" in name or "Autorun" in name:
        return "persistence"
    if "Registry" in name or "Timeline" in name:
        return "triage"
    return None


def derive_supported_os(velo_artifact: dict) -> list[str]:
    """Extract OS support from the Velo artifact name prefix."""
    name = velo_artifact.get("name", "")
    prefix = name.split(".", 1)[0].lower()
    if prefix in ("windows", "linux", "darwin", "macos"):
        return [prefix if prefix != "macos" else "darwin"]
    if prefix in ("generic", "server"):
        return ["windows", "linux", "darwin"]
    return []


async def _sync_tenant_catalog(db: AsyncSession, tenant: TenantModel) -> None:
    """Upsert artifacts for a single tenant. Preserves admin overrides."""
    velo_client = get_velo_client()
    velo_artifacts = await velo_client.list_artifacts(org_id=tenant.velo_org_id)

    seen_names: set[str] = set()
    for va in velo_artifacts:
        name = va.get("name")
        if not name:
            continue
        seen_names.add(name)

        result = await db.execute(
            select(ForensicArtifactModel).where(
                ForensicArtifactModel.tenant_id == tenant.id,
                ForensicArtifactModel.name == name,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.description = va.get("description")
            existing.artifact_type = va.get("type", "CLIENT")
            existing.supported_os = derive_supported_os(va)
            existing.parameters_schema = va.get("parameters", []) or []
            existing.last_synced_at = datetime.now(timezone.utc)
            existing.is_active = True
        else:
            db.add(ForensicArtifactModel(
                tenant_id=tenant.id,
                name=name,
                description=va.get("description"),
                artifact_type=va.get("type", "CLIENT"),
                supported_os=derive_supported_os(va),
                parameters_schema=va.get("parameters", []) or [],
                is_destructive=detect_destructive(name),
                requires_evidence_handling=detect_evidence(name),
                category=infer_category(name),
                is_featured=False,
                last_synced_at=datetime.now(timezone.utc),
            ))

    if seen_names:
        await db.execute(
            update(ForensicArtifactModel)
            .where(
                ForensicArtifactModel.tenant_id == tenant.id,
                ForensicArtifactModel.name.notin_(seen_names),
                ForensicArtifactModel.is_active.is_(True),
            )
            .values(is_active=False)
        )


async def sync_all_tenants() -> None:
    """Iterate every tenant with ``velo_org_id`` set and sync its catalog."""
    from backend.src.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TenantModel).where(TenantModel.velo_org_id.isnot(None))
        )
        for tenant in result.scalars().all():
            try:
                await _sync_tenant_catalog(db, tenant)
            except Exception as e:
                logger.error(
                    "Catalog sync failed for tenant %s: %s", tenant.id, e
                )
        await db.commit()
