import asyncio
import logging
from collections import defaultdict
from typing import Callable, Awaitable

from backend.src.core.events.base import BaseEvent

logger = logging.getLogger(__name__)

Handler = Callable[[BaseEvent], Awaitable[None]]


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: BaseEvent) -> None:
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            return
        results = await asyncio.gather(
            *[handler(event) for handler in handlers],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.error(
                    "Event handler error for %s: %s",
                    event.event_type,
                    result,
                    exc_info=result,
                )


_event_bus = EventBus()


def get_event_bus() -> EventBus:
    return _event_bus


# Module-level alias for convenience imports
event_bus = _event_bus
