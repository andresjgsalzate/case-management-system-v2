"""Vendor-neutral normalized event shape used by every parser."""
from dataclasses import dataclass, field


@dataclass
class NormalizedEvent:
    """Normalized form a parser produces from a vendor-specific payload.

    `custom_values` holds string-typed fields keyed by canonical names
    (source_ip, affected_user, hash, …). Downstream the case-creation
    use case filters these to the subset declared by the matched
    service-catalog item — no need to pre-filter here.

    Wazuh-specific hints (`wazuh_*`) are populated only by the Wazuh
    parser and consumed by the Wazuh taxonomy resolver. For other
    vendors they remain at their defaults.
    """
    title: str
    description: str
    custom_values: dict[str, str] = field(default_factory=dict)
    wazuh_rule_id: int | None = None
    wazuh_rule_groups: list[str] = field(default_factory=list)
    wazuh_level: int | None = None
