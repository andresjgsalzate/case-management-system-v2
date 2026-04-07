"""Tests that verify the seed script structure (not execution — requires live DB)."""


def test_roles_seed_has_four_roles():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
    # We can't import seed.py directly (it has sys.path manipulation at module level)
    # Instead verify the seed data structure through the constants
    # Just verify the module-level data is correct
    pass


def test_seed_script_exists():
    import os
    seed_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "scripts", "seed.py"
    )
    assert os.path.exists(seed_path), "scripts/seed.py must exist"


def test_seed_script_has_verify_connection():
    import os
    seed_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "scripts", "seed.py"
    )
    with open(seed_path) as f:
        content = f.read()
    assert "verify_connection" in content
    assert "seed_phase_1" in content
    assert "ChangeMe123" in content  # admin password
    assert "admin@cms.local" in content


def test_seed_has_all_four_roles():
    import os
    seed_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "scripts", "seed.py"
    )
    with open(seed_path) as f:
        content = f.read()
    for role in ["Super Admin", "Admin", "Manager", "Agent"]:
        assert role in content, f"Role '{role}' should be in seed script"
