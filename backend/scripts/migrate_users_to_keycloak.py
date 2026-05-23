"""Migrate CMS users to Keycloak (sub-spec 09 Task 2.4).

Reads users + roles from the CMS database and provisions matching
accounts in Keycloak. ``users.id`` is sent as the Keycloak user ``id``
so the ``sub`` claim on issued tokens lines up with the existing
``users.id`` column without re-keying the database.

The script is idempotent in spirit but NOT atomically — it stops at the
first hard error. Re-runs against partially-migrated realms will hit
``409 Conflict`` on the second pass; either delete the conflicting users
first or pass ``--skip-existing`` (TODO; not implemented in v1).

Usage:
    # Preview without writing anything
    python -m backend.scripts.migrate_users_to_keycloak --dry-run

    # Live (uses Keycloak master-realm bootstrap admin)
    KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD=...  \\
        python -m backend.scripts.migrate_users_to_keycloak \\
            --keycloak-url http://localhost:8080 \\
            --realm cms

    # Skip the password-reset email blast (handy for dev with fake addrs)
    python -m backend.scripts.migrate_users_to_keycloak --skip-password-reset
"""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

from backend.src.modules.auth.keycloak_client import KeycloakAdminClient


def split_full_name(full_name: str) -> tuple[str, str]:
    """Return (first, last) — split on the first whitespace.

    Keycloak stores ``firstName`` and ``lastName`` separately. CMS stores
    ``full_name`` as one string, so we split on the first space and treat
    the remainder as the surname. Single-word names map to first only.
    """
    parts = full_name.strip().split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def build_user_payload(user: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy ``UserModel`` row into Keycloak's create-user JSON."""
    first, last = split_full_name(user.full_name)
    return {
        "id": user.id,
        "username": user.email,
        "email": user.email,
        "firstName": first,
        "lastName": last,
        "enabled": bool(user.is_active),
        "emailVerified": True,
        "attributes": {
            "tenant_id": [user.tenant_id or "default"],
        },
    }


async def migrate(
    *,
    db_url: str,
    kc_server_url: str,
    realm: str,
    admin_user: str,
    admin_password: str,
    dry_run: bool = False,
    skip_password_reset: bool = False,
) -> None:
    # Imports here, not at module top, so `--help` works without the
    # DATABASE_URL env var (model imports transitively instantiate Settings).
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    # Side-effect import: register UserSessionModel + sibling auth models
    # with the SQLAlchemy registry so UserModel's relationships resolve.
    from backend.src.modules.auth.infrastructure import models as _  # noqa: F401
    from backend.src.modules.roles.infrastructure.models import RoleModel
    from backend.src.modules.users.infrastructure.models import UserModel

    engine = create_async_engine(db_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as db:
        rows = (
            await db.execute(
                select(UserModel, RoleModel).outerjoin(
                    RoleModel, UserModel.role_id == RoleModel.id
                )
            )
        ).all()

    try:
        if dry_run:
            print(f"DRY RUN: would migrate {len(rows)} users")
            for user, role in rows:
                payload = build_user_payload(user)
                role_name = role.name if role else "<no role>"
                print(
                    f"  {payload['email']:<35} "
                    f"role={role_name:<15} "
                    f"tenant={payload['attributes']['tenant_id'][0]:<12} "
                    f"id={user.id}"
                )
            return

        admin = KeycloakAdminClient.from_admin_password(
            server_url=kc_server_url,
            realm=realm,
            admin_user=admin_user,
            admin_password=admin_password,
            verify_ssl=False,  # dev self-signed
        )
        try:
            realm_roles = await admin.list_realm_roles()
            role_index = {r["name"]: r for r in realm_roles}

            for user, role in rows:
                payload = build_user_payload(user)
                print(f"Creating {payload['email']}…")
                user_id = await admin.create_user(payload)

                if role is not None:
                    realm_role = role_index.get(role.name)
                    if realm_role:
                        await admin.assign_realm_roles(user_id, [realm_role])
                        print(f"  assigned realm role: {role.name}")
                    else:
                        print(
                            f"  WARN: realm role '{role.name}' not found "
                            "in Keycloak — skipping role assignment"
                        )

                if not skip_password_reset:
                    await admin.send_password_reset(user_id)
                    print("  password-reset email sent")
        finally:
            await admin.aclose()
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate CMS users to Keycloak.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended actions without contacting Keycloak.",
    )
    parser.add_argument(
        "--keycloak-url",
        default=os.environ.get("KEYCLOAK_URL", "http://localhost:8080"),
        help="Keycloak base URL (without realm). Default: %(default)s",
    )
    parser.add_argument(
        "--realm", default="cms", help="Target realm. Default: %(default)s"
    )
    parser.add_argument(
        "--admin-user",
        default=os.environ.get("KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME", "admin"),
    )
    parser.add_argument(
        "--admin-password",
        default=os.environ.get("KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD", ""),
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Override DATABASE_URL from Settings.",
    )
    parser.add_argument(
        "--skip-password-reset",
        action="store_true",
        help="Don't trigger the UPDATE_PASSWORD email blast.",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.admin_password:
        parser.error(
            "--admin-password required for non-dry-run "
            "(or set KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD)"
        )

    if args.db_url:
        db_url = args.db_url
    else:
        from backend.src.core.config import get_settings
        db_url = get_settings().DATABASE_URL

    asyncio.run(
        migrate(
            db_url=db_url,
            kc_server_url=args.keycloak_url,
            realm=args.realm,
            admin_user=args.admin_user,
            admin_password=args.admin_password,
            dry_run=args.dry_run,
            skip_password_reset=args.skip_password_reset,
        )
    )


if __name__ == "__main__":
    main()
