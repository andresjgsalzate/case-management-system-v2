def test_case_transfer_model_columns():
    from backend.src.modules.cases.infrastructure.transfer_models import CaseTransferModel
    cols = {c.name for c in CaseTransferModel.__table__.columns}
    expected = {
        "id", "tenant_id", "case_id", "from_user_id", "from_level",
        "to_user_id", "to_team_id", "to_level",
        "transfer_type", "reason", "created_at",
    }
    assert expected <= cols


def test_case_transfer_tablename():
    from backend.src.modules.cases.infrastructure.transfer_models import CaseTransferModel
    assert CaseTransferModel.__tablename__ == "case_transfers"


def test_classify_transfer_escalate():
    from backend.src.modules.cases.application.transfer_use_cases import classify_transfer
    assert classify_transfer(from_level=1, to_level=2) == "escalate"


def test_classify_transfer_reassign():
    from backend.src.modules.cases.application.transfer_use_cases import classify_transfer
    assert classify_transfer(from_level=1, to_level=1) == "reassign"


def test_classify_transfer_de_escalate():
    from backend.src.modules.cases.application.transfer_use_cases import classify_transfer
    assert classify_transfer(from_level=2, to_level=1) == "de-escalate"


def test_transfer_dto_rejects_empty_reason():
    from backend.src.modules.cases.application.transfer_dtos import TransferCaseDTO
    import pytest
    with pytest.raises(Exception):
        TransferCaseDTO(to_user_id="u2", reason="   ")


def test_transfer_dto_accepts_valid():
    from backend.src.modules.cases.application.transfer_dtos import TransferCaseDTO
    dto = TransferCaseDTO(to_user_id="u2", reason="needs N2 expertise")
    assert dto.reason == "needs N2 expertise"


def test_router_registers_transfer_endpoints():
    from backend.src.modules.cases.router import router
    paths = {route.path for route in router.routes}
    assert "/api/v1/cases/{case_id}/transfer" in paths
    assert "/api/v1/cases/{case_id}/transfers" in paths
