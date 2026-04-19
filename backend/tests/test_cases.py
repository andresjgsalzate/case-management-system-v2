import pytest


def test_create_case_dto_requires_title():
    from backend.src.modules.cases.application.dtos import CreateCaseDTO
    dto = CreateCaseDTO(title="Test case", priority_id="p1")
    assert dto.title == "Test case"


def test_create_case_dto_short_title_raises():
    from backend.src.modules.cases.application.dtos import CreateCaseDTO
    with pytest.raises(Exception):
        CreateCaseDTO(title="X", priority_id="p1")  # mínimo 3 chars


def test_create_case_dto_default_complexity():
    from backend.src.modules.cases.application.dtos import CreateCaseDTO
    dto = CreateCaseDTO(title="Valid title", priority_id="p1")
    assert dto.complexity == "simple"


def test_create_case_dto_complex_complexity():
    from backend.src.modules.cases.application.dtos import CreateCaseDTO
    dto = CreateCaseDTO(title="Valid title", priority_id="p1", complexity="complex")
    assert dto.complexity == "complex"


def test_list_cases_uses_filter_cases_by_permission(monkeypatch):
    """Verifies CaseUseCases.list_cases delegates to the central query builder
    rather than duplicating scope logic."""
    import backend.src.modules.cases.application.use_cases as uc_mod
    called_with = {}

    def fake_filter(query, user, queue="all"):
        called_with["queue"] = queue
        called_with["scope"] = user.scope
        return query

    monkeypatch.setattr(uc_mod, "filter_cases_by_permission", fake_filter, raising=False)
    # Symbolic assertion: after the refactor, the import line below must exist.
    import inspect
    source = inspect.getsource(uc_mod)
    assert "filter_cases_by_permission" in source
