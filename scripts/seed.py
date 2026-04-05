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

from dotenv import load_dotenv  # type: ignore[import]

# Load .env from backend/
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from src.core.config import get_settings  # noqa: E402
from src.core.database import AsyncSessionLocal  # noqa: E402


async def verify_connection() -> bool:
    """Verify PostgreSQL connectivity before seeding."""
    from sqlalchemy import text
    settings = get_settings()
    print(f"Connecting to: {settings.DATABASE_URL.split('@')[-1]}")  # Hide credentials
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
        print("✓ Database connection OK")
        return True
    except Exception as exc:
        print(f"✗ Database connection failed: {exc}")
        return False


# ─── Phase 1: Users, Roles, Teams ───────────────────────────────────────────
async def seed_phase_1(session) -> None:
    """Seed users, roles, and teams. Populated in Phase 1."""
    pass


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
        await session.commit()
    print("✓ Seed complete")


if __name__ == "__main__":
    asyncio.run(main())
