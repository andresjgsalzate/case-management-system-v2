"""
Motor de evaluación de reglas de automatización.

Cada condición es un dict {field, operator, value}.
El operador se evalúa contra el contexto del evento (también un dict).
"""
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RuleCondition:
    field: str
    operator: str  # equals | not_equals | contains | not_contains | in | not_in | starts_with | ends_with
    value: Any


@dataclass
class RuleAction:
    action_type: str  # assign_agent | change_priority | change_status | send_notification | add_tag
    params: dict[str, Any]


def evaluate_condition(condition: RuleCondition, context: dict[str, Any]) -> bool:
    """
    Evalúa una condición contra el contexto del evento.
    Retorna False si el campo no existe en el contexto.
    """
    if condition.field not in context:
        return False
    actual = context[condition.field]
    expected = condition.value

    match condition.operator:
        case "equals":
            return str(actual).lower() == str(expected).lower()
        case "not_equals":
            return str(actual).lower() != str(expected).lower()
        case "contains":
            return str(expected).lower() in str(actual).lower()
        case "not_contains":
            return str(expected).lower() not in str(actual).lower()
        case "in":
            return actual in (expected if isinstance(expected, list) else [expected])
        case "not_in":
            return actual not in (expected if isinstance(expected, list) else [expected])
        case "starts_with":
            return str(actual).lower().startswith(str(expected).lower())
        case "ends_with":
            return str(actual).lower().endswith(str(expected).lower())
        case _:
            logger.warning("Operador desconocido en regla: %s", condition.operator)
            return False


def evaluate_rule(
    conditions: list[dict[str, Any]],
    context: dict[str, Any],
    logic: str = "AND",
) -> bool:
    """
    Evalúa todas las condiciones con lógica AND u OR.
    Sin condiciones, la regla siempre se activa.
    """
    if not conditions:
        return True

    parsed = [RuleCondition(**c) for c in conditions]
    results = [evaluate_condition(c, context) for c in parsed]

    if logic == "OR":
        return any(results)
    return all(results)  # AND por defecto
