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
