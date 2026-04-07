import pytest


def test_valid_transition_allowed():
    from backend.src.modules.case_statuses.application.use_cases import validate_transition
    current_transitions = ["in_progress", "closed"]
    assert validate_transition("in_progress", current_transitions) is True


def test_invalid_transition_raises():
    from backend.src.modules.case_statuses.application.use_cases import validate_transition
    from backend.src.core.exceptions import BusinessRuleError
    with pytest.raises(BusinessRuleError) as exc_info:
        validate_transition("resolved", ["in_progress", "closed"])
    assert "not allowed" in str(exc_info.value).lower()


def test_valid_transition_to_self_not_allowed():
    from backend.src.modules.case_statuses.application.use_cases import validate_transition
    from backend.src.core.exceptions import BusinessRuleError
    with pytest.raises(BusinessRuleError):
        validate_transition("open", ["in_progress"])  # 'open' no está en la lista
