def evaluate_condition(field_value: str, operator: str, value: str) -> bool:
    """Evalúa una condición individual contra un valor de campo."""
    field_lower = field_value.lower()
    value_lower = value.lower()
    if operator == "contains":
        return value_lower in field_lower
    if operator == "equals":
        return field_lower == value_lower
    if operator == "starts_with":
        return field_lower.startswith(value_lower)
    if operator == "ends_with":
        return field_lower.endswith(value_lower)
    return False


def apply_rules(case_title: str, rules: list[dict]) -> dict | None:
    """
    Evalúa reglas en orden de prioridad (menor número = mayor prioridad).
    Devuelve el resultado de la primera regla donde TODAS las condiciones coincidan, o None.
    """
    sorted_rules = sorted(rules, key=lambda r: r.get("priority", 999))
    for rule in sorted_rules:
        conditions = rule.get("conditions", [])
        if not conditions:
            continue
        all_match = all(
            evaluate_condition(
                c.get("field_value", case_title),
                c.get("operator", "contains"),
                c.get("value", ""),
            )
            for c in conditions
        )
        if all_match:
            return rule.get("result")
    return None
