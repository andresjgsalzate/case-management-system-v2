from dataclasses import dataclass, field
from typing import Literal

ScopeType = Literal["own", "team", "all"]
VALID_MODULES = {
    "cases", "users", "teams", "roles", "sla", "knowledge", "audit",
    "metrics", "dispositions", "todos", "notes", "time", "classification",
    "attachments", "notifications", "automation", "applications", "origins",
}
VALID_ACTIONS = {
    "create", "read", "update", "delete", "manage", "export",
    "archive", "assign", "publish", "transition", "review", "publish_direct",
}


@dataclass
class Permission:
    role_id: str
    module: str
    action: str
    scope: ScopeType
    id: str = ""

    def __post_init__(self):
        if self.scope not in ("own", "team", "all"):
            raise ValueError(f"Invalid scope: {self.scope}. Must be own/team/all")


@dataclass
class Role:
    name: str
    id: str = ""
    tenant_id: str | None = None
    description: str | None = None
    permissions: list[Permission] = field(default_factory=list)
