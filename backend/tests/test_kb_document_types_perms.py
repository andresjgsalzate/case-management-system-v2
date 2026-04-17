import os
import sys


def test_perms_migration_file_exists():
    path = os.path.join(
        os.path.dirname(__file__), "..", "alembic", "versions",
        "b8d9e0f1a2b3_add_kb_document_types_perms.py",
    )
    assert os.path.exists(path)


def test_seed_admin_has_document_types_perms():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from scripts.seed import ROLES_SEED
    admin = next(r for r in ROLES_SEED if r["name"] == "Admin")
    perms = [(p["module"], p["action"]) for p in admin["permissions"]]
    assert ("document_types", "read") in perms
    assert ("document_types", "create") in perms
    assert ("document_types", "update") in perms
    assert ("document_types", "delete") in perms


def test_seed_all_roles_have_document_types_read():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from scripts.seed import ROLES_SEED
    for role in ROLES_SEED:
        perms = [(p["module"], p["action"]) for p in role["permissions"]]
        assert ("document_types", "read") in perms, (
            f"Role {role['name']} missing document_types:read"
        )
