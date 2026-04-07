from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class BaseEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: dict[str, Any] = field(default_factory=dict)
    tenant_id: str = field(default="default")
    actor_id: str = field(default="")
    event_name: str = field(default="")

    @property
    def event_type(self) -> str:
        return self.event_name or self.__class__.__name__
