"""Hardcoded Wazuh alert parser.

Spec ref: `docs/superpowers/specs/2026-05-10-inbound-integrations-wazuh-design.md` §4.5.

Why hardcoded instead of JSONPath? Wazuh's payload shape is stable across
versions and rich enough (nested rule/agent/data) that mapping table rows
would duplicate the same paths for every deployment. The hardcoded path
also documents *which* fields the rest of the pipeline depends on.
"""
from backend.src.modules.integrations.application.parsers.normalized_event import (
    NormalizedEvent,
)

# Public title and full_log payloads can be arbitrarily large; cap to keep
# downstream case payloads bounded.
_TITLE_MAX = 500
_FULL_LOG_MAX = 5000


def parse_wazuh(payload: dict, source) -> NormalizedEvent:
    """Extract canonical fields from a standard Wazuh alert payload.

    `source` is accepted for parity with other parsers (and future per-source
    overrides) but the hardcoded parser does not consult it today.
    """
    rule = payload.get("rule") or {}
    agent = payload.get("agent") or {}
    data = payload.get("data") or {}

    title = rule.get("description") or f"Wazuh alert {rule.get('id')}"
    description = _build_wazuh_description(payload)

    # Known Wazuh data fields → canonical custom_value keys. Only emit a key
    # when its source value is truthy — keeps custom_values free of empty noise.
    custom_values: dict[str, str] = {}
    _set_if(custom_values, "source_ip", data.get("srcip"))
    _set_if(custom_values, "destination_ip", data.get("dstip"))
    _set_if(custom_values, "affected_user", data.get("user"))
    _set_if(custom_values, "target_user", data.get("dstuser"))
    _set_if(custom_values, "source_user", data.get("srcuser"))
    _set_if(custom_values, "process_name", data.get("process"))
    _set_if(custom_values, "command_executed", data.get("command"))
    _set_if(custom_values, "url", data.get("url"))
    _set_if(custom_values, "hash", data.get("hash"))
    _set_if(custom_values, "file_path", data.get("file"))
    _set_if(custom_values, "hostname", agent.get("name"))
    _set_if(custom_values, "host_ip", agent.get("ip"))
    if rule.get("level") is not None:
        custom_values["wazuh_level"] = str(rule["level"])

    # Always-included Wazuh metadata (downstream resolvers depend on these).
    custom_values["wazuh_rule_id"] = str(rule.get("id"))
    custom_values["wazuh_rule_groups"] = ",".join(rule.get("groups") or [])
    custom_values["wazuh_agent_id"] = agent.get("id") or ""
    custom_values["wazuh_full_log"] = (payload.get("full_log") or "")[:_FULL_LOG_MAX]

    if rule.get("firedtimes"):
        custom_values["wazuh_firedtimes"] = str(rule["firedtimes"])

    return NormalizedEvent(
        title=title[:_TITLE_MAX],
        description=description,
        custom_values=custom_values,
        wazuh_rule_id=rule.get("id"),
        wazuh_rule_groups=list(rule.get("groups") or []),
        wazuh_level=rule.get("level"),
    )


def _build_wazuh_description(payload: dict) -> str:
    """Compact human-readable summary of the alert for the case body."""
    rule = payload.get("rule") or {}
    agent = payload.get("agent") or {}
    parts: list[str] = []
    if rule.get("description"):
        parts.append(rule["description"])
    if agent.get("name"):
        parts.append(f"Host: {agent['name']}")
    if rule.get("id") is not None:
        parts.append(f"Rule ID: {rule['id']}")
    if rule.get("level") is not None:
        parts.append(f"Level: {rule['level']}")
    return " · ".join(parts) or "Wazuh alert"


def _set_if(target: dict, key: str, value) -> None:
    """Set target[key] only when value is truthy (non-empty/non-None)."""
    if value:
        target[key] = value
