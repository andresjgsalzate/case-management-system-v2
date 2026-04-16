def test_migration_file_exists():
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "alembic", "versions",
        "b1c2d3e4f5a6_add_kb_create_perms.py"
    )
    assert os.path.exists(path)

def test_seed_agent_has_kb_create():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from scripts.seed import ROLES_SEED
    agent = next(r for r in ROLES_SEED if r["name"] == "Agent")
    perms = [(p["module"], p["action"]) for p in agent["permissions"]]
    assert ("knowledge_base", "create") in perms

def test_seed_manager_has_kb_create():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from scripts.seed import ROLES_SEED
    manager = next(r for r in ROLES_SEED if r["name"] == "Manager")
    perms = [(p["module"], p["action"]) for p in manager["permissions"]]
    assert ("knowledge_base", "create") in perms
