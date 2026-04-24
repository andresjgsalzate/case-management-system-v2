import os
import pytest


def test_alembic_ini_exists():
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    alembic_ini = os.path.join(base, "backend", "alembic.ini")
    assert os.path.exists(alembic_ini), "alembic.ini should exist in backend/"


def test_alembic_env_exists():
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_py = os.path.join(base, "backend", "alembic", "env.py")
    assert os.path.exists(env_py), "alembic/env.py should exist"


def test_alembic_versions_dir_exists():
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    versions = os.path.join(base, "backend", "alembic", "versions")
    assert os.path.isdir(versions), "alembic/versions/ directory should exist"


def test_alembic_env_imports_base():
    # Verify alembic/env.py references our Base metadata
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_py = os.path.join(base, "backend", "alembic", "env.py")
    with open(env_py) as f:
        content = f.read()
    assert "Base.metadata" in content
    assert "run_async_migrations" in content


def test_helpdesk_levels_migration_present():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "c1d2e3f4a5b6_helpdesk_levels_and_transfers.py"
    assert path.exists(), f"migration file missing: {path}"
    spec = importlib.util.spec_from_file_location("migration_c1d2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "c1d2e3f4a5b6"
    assert module.down_revision == "1f35f05d8d94"
    assert callable(module.upgrade)
    assert callable(module.downgrade)
