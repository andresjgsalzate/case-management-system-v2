def test_activity_description_case_created():
    from backend.src.modules.activity.application.handlers import build_activity_description
    desc = build_activity_description(
        "case.created", {"case_number": "CASE-0001", "title": "Test"}
    )
    assert "CASE-0001" in desc


def test_activity_description_status_changed():
    from backend.src.modules.activity.application.handlers import build_activity_description
    desc = build_activity_description(
        "case.status_changed", {"from_status": "Open", "to_status": "In Progress"}
    )
    assert "Open" in desc
    assert "In Progress" in desc


def test_activity_description_unknown_event():
    from backend.src.modules.activity.application.handlers import build_activity_description
    desc = build_activity_description("unknown.event", {})
    assert desc  # siempre devuelve algo


def test_activity_description_case_closed():
    from backend.src.modules.activity.application.handlers import build_activity_description
    desc = build_activity_description("case.closed", {"case_id": "123"})
    assert "cerrado" in desc.lower()
