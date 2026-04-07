"""Tests del motor de evaluación de reglas de automatización."""


def test_condition_equals_matches():
    from backend.src.modules.automation.application.engine import RuleCondition, evaluate_condition
    condition = RuleCondition(field="priority", operator="equals", value="alta")
    assert evaluate_condition(condition, {"priority": "alta"}) is True


def test_condition_equals_case_insensitive():
    from backend.src.modules.automation.application.engine import RuleCondition, evaluate_condition
    condition = RuleCondition(field="priority", operator="equals", value="ALTA")
    assert evaluate_condition(condition, {"priority": "alta"}) is True


def test_condition_equals_no_match():
    from backend.src.modules.automation.application.engine import RuleCondition, evaluate_condition
    condition = RuleCondition(field="priority", operator="equals", value="alta")
    assert evaluate_condition(condition, {"priority": "media"}) is False


def test_condition_contains():
    from backend.src.modules.automation.application.engine import RuleCondition, evaluate_condition
    condition = RuleCondition(field="title", operator="contains", value="VPN")
    assert evaluate_condition(condition, {"title": "Problema con VPN corporativa"}) is True
    assert evaluate_condition(condition, {"title": "Error de impresora"}) is False


def test_condition_not_equals():
    from backend.src.modules.automation.application.engine import RuleCondition, evaluate_condition
    condition = RuleCondition(field="status", operator="not_equals", value="cerrado")
    assert evaluate_condition(condition, {"status": "abierto"}) is True
    assert evaluate_condition(condition, {"status": "cerrado"}) is False


def test_condition_in_list():
    from backend.src.modules.automation.application.engine import RuleCondition, evaluate_condition
    condition = RuleCondition(field="origin", operator="in", value=["email", "portal"])
    assert evaluate_condition(condition, {"origin": "email"}) is True
    assert evaluate_condition(condition, {"origin": "telefono"}) is False


def test_condition_not_in_list():
    from backend.src.modules.automation.application.engine import RuleCondition, evaluate_condition
    condition = RuleCondition(field="origin", operator="not_in", value=["email", "portal"])
    assert evaluate_condition(condition, {"origin": "telefono"}) is True
    assert evaluate_condition(condition, {"origin": "email"}) is False


def test_missing_field_returns_false():
    from backend.src.modules.automation.application.engine import RuleCondition, evaluate_condition
    condition = RuleCondition(field="nonexistent", operator="equals", value="x")
    assert evaluate_condition(condition, {"priority": "alta"}) is False


def test_unknown_operator_returns_false():
    from backend.src.modules.automation.application.engine import RuleCondition, evaluate_condition
    condition = RuleCondition(field="priority", operator="regex", value="alt.*")
    assert evaluate_condition(condition, {"priority": "alta"}) is False


def test_evaluate_rule_and_all_match():
    from backend.src.modules.automation.application.engine import evaluate_rule
    conditions = [
        {"field": "priority", "operator": "equals", "value": "alta"},
        {"field": "status", "operator": "equals", "value": "abierto"},
    ]
    assert evaluate_rule(conditions, {"priority": "alta", "status": "abierto"}, "AND") is True


def test_evaluate_rule_and_partial_fail():
    from backend.src.modules.automation.application.engine import evaluate_rule
    conditions = [
        {"field": "priority", "operator": "equals", "value": "alta"},
        {"field": "status", "operator": "equals", "value": "cerrado"},
    ]
    assert evaluate_rule(conditions, {"priority": "alta", "status": "abierto"}, "AND") is False


def test_evaluate_rule_or_partial_match():
    from backend.src.modules.automation.application.engine import evaluate_rule
    conditions = [
        {"field": "priority", "operator": "equals", "value": "alta"},
        {"field": "status", "operator": "equals", "value": "cerrado"},
    ]
    assert evaluate_rule(conditions, {"priority": "alta", "status": "abierto"}, "OR") is True


def test_evaluate_rule_empty_conditions_always_true():
    from backend.src.modules.automation.application.engine import evaluate_rule
    assert evaluate_rule([], {}, "AND") is True
    assert evaluate_rule([], {"priority": "alta"}, "OR") is True


def test_starts_with_and_ends_with():
    from backend.src.modules.automation.application.engine import RuleCondition, evaluate_condition
    cond_start = RuleCondition(field="title", operator="starts_with", value="Error")
    cond_end = RuleCondition(field="title", operator="ends_with", value="VPN")
    ctx = {"title": "Error de VPN"}
    assert evaluate_condition(cond_start, ctx) is True
    assert evaluate_condition(cond_end, ctx) is True
