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
