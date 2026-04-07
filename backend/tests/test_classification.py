import pytest


def test_contains_operator_match():
    from backend.src.modules.classification.application.rule_engine import evaluate_condition
    assert evaluate_condition("Mi sistema urgente falla", "contains", "urgente") is True


def test_contains_operator_no_match():
    from backend.src.modules.classification.application.rule_engine import evaluate_condition
    assert evaluate_condition("Sistema normal", "contains", "urgente") is False


def test_equals_operator():
    from backend.src.modules.classification.application.rule_engine import evaluate_condition
    assert evaluate_condition("critical", "equals", "critical") is True


def test_starts_with_operator():
    from backend.src.modules.classification.application.rule_engine import evaluate_condition
    assert evaluate_condition("Error en producción", "starts_with", "error") is True


def test_apply_rules_returns_first_match():
    from backend.src.modules.classification.application.rule_engine import apply_rules
    rules = [
        {
            "conditions": [{"field_value": "urgente falla", "operator": "contains", "value": "urgente"}],
            "result": {"urgency": "high"},
            "priority": 1,
        },
        {
            "conditions": [{"field_value": "urgente falla", "operator": "contains", "value": "urgente"}],
            "result": {"urgency": "medium"},
            "priority": 2,
        },
    ]
    result = apply_rules("caso urgente", rules)
    assert result["urgency"] == "high"


def test_apply_rules_no_match_returns_none():
    from backend.src.modules.classification.application.rule_engine import apply_rules
    rules = [
        {
            "conditions": [{"field_value": "normal", "operator": "contains", "value": "critico"}],
            "result": {"urgency": "high"},
            "priority": 1,
        }
    ]
    result = apply_rules("caso normal", rules)
    assert result is None


def test_apply_rules_all_conditions_must_match():
    from backend.src.modules.classification.application.rule_engine import apply_rules
    # Dos condiciones, solo una coincide → no debe aplicar
    rules = [
        {
            "conditions": [
                {"field_value": "caso urgente", "operator": "contains", "value": "urgente"},
                {"field_value": "caso urgente", "operator": "contains", "value": "critico"},
            ],
            "result": {"urgency": "critical"},
            "priority": 1,
        }
    ]
    result = apply_rules("caso urgente", rules)
    assert result is None
