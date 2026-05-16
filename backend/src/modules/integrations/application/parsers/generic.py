"""Generic parser driven by integration_mappings JSONPath rows.

Used for any source_type other than 'wazuh' (Splunk, Sentinel, CrowdStrike,
QRadar, custom). Each `IntegrationMappingModel` row is a tuple of:
  (target_field, json_path, transform, default_value, is_required)

`target_field` either matches a `NormalizedEvent` slot ('title', 'description',
'taxonomy_code') or uses the `custom.<key>` prefix to land in custom_values.

`transform` is optional and supports a small fixed vocabulary plus the
parametric `truncate(N)` and `regex:<pattern>` forms. Unknown names no-op
rather than raising — bad mapping config should never crash a webhook.
"""
import re

from jsonpath_ng import parse as jsonpath_parse

from backend.src.core.exceptions import ValidationError
from backend.src.modules.integrations.application.parsers.normalized_event import (
    NormalizedEvent,
)


_TRANSFORMS = {
    "uppercase": lambda v: str(v).upper(),
    "lowercase": lambda v: str(v).lower(),
    # pass-through; downstream parses ISO strings as needed:
    "parse_iso_datetime": lambda v: v,
}


def _apply_transform(value, transform: str | None):
    """Apply a named transform to `value`, or return unchanged on unknown name."""
    if not transform:
        return value
    if transform.startswith("truncate("):
        try:
            n = int(transform[len("truncate("):-1])
        except ValueError:
            return value
        return str(value)[:n]
    if transform.startswith("regex:"):
        pattern = transform[len("regex:"):]
        m = re.search(pattern, str(value))
        return m.group(0) if m else None
    fn = _TRANSFORMS.get(transform)
    return fn(value) if fn else value


async def parse_via_mappings(payload: dict, mappings: list) -> NormalizedEvent:
    """Extract fields from `payload` driven by `mappings` rows.

    Raises ValidationError if a required mapping has no match and no default.
    Async signature mirrors `parse_wazuh`-call-site contract from the use case
    even though the body itself is purely CPU-bound.
    """
    extracted: dict = {}
    custom_values: dict[str, str] = {}

    for m in mappings:
        expr = jsonpath_parse(m.json_path)
        matches = [match.value for match in expr.find(payload)]

        if matches:
            value = _apply_transform(matches[0], m.transform)
        elif m.default_value is not None:
            value = m.default_value
        elif m.is_required:
            raise ValidationError(
                f"Required field '{m.target_field}' not found in payload",
            )
        else:
            continue

        if m.target_field.startswith("custom."):
            custom_values[m.target_field[len("custom."):]] = str(value)
        else:
            extracted[m.target_field] = value

    return NormalizedEvent(
        title=str(extracted.get("title", "Untitled event"))[:500],
        description=str(extracted.get("description", "")),
        custom_values=custom_values,
    )
