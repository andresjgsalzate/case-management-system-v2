import os


def test_migration_file_exists():
    path = os.path.join(
        os.path.dirname(__file__), "..", "alembic", "versions",
        "b7c8d9e0f1a2_add_kb_document_types.py",
    )
    assert os.path.exists(path)


def test_migration_defines_revision_ids():
    path = os.path.join(
        os.path.dirname(__file__), "..", "alembic", "versions",
        "b7c8d9e0f1a2_add_kb_document_types.py",
    )
    with open(path, encoding="utf-8") as f:
        src = f.read()
    assert 'revision = "b7c8d9e0f1a2"' in src
    assert (
        'down_revision = "fc1a2b3c4d5e"' in src
        or 'down_revision = "a2b3c4d5e6f7"' in src
        or 'down_revision = "b1c2d3e4f5a6"' in src
    )


def test_migration_seeds_four_document_types():
    path = os.path.join(
        os.path.dirname(__file__), "..", "alembic", "versions",
        "b7c8d9e0f1a2_add_kb_document_types.py",
    )
    with open(path, encoding="utf-8") as f:
        src = f.read()
    for code in ("guia", "procedimiento", "incidente", "faq"):
        assert f'"{code}"' in src
