import pytest
import asyncio
from backend.src.core.events.base import BaseEvent
from backend.src.core.events.bus import EventBus


class CaseCreated(BaseEvent):
    pass


class TestBaseEvent:
    def test_event_has_id_and_timestamp(self):
        event = CaseCreated(payload={"case_id": 1})
        assert event.event_id
        assert event.occurred_at is not None
        assert event.event_type == "CaseCreated"

    def test_event_id_is_unique(self):
        e1 = CaseCreated()
        e2 = CaseCreated()
        assert e1.event_id != e2.event_id


class TestEventBus:
    @pytest.mark.asyncio
    async def test_handler_is_called(self):
        bus = EventBus()
        received = []

        async def handler(event: BaseEvent):
            received.append(event)

        bus.subscribe("CaseCreated", handler)
        event = CaseCreated(payload={"case_id": 42})
        await bus.publish(event)

        assert len(received) == 1
        assert received[0].payload["case_id"] == 42

    @pytest.mark.asyncio
    async def test_no_handlers_does_not_raise(self):
        bus = EventBus()
        event = CaseCreated()
        await bus.publish(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_propagate(self):
        bus = EventBus()

        async def failing_handler(event: BaseEvent):
            raise ValueError("Handler failed")

        bus.subscribe("CaseCreated", failing_handler)
        event = CaseCreated()
        await bus.publish(event)  # Should not raise despite handler failure

    @pytest.mark.asyncio
    async def test_multiple_handlers_all_called(self):
        bus = EventBus()
        calls = []

        async def h1(e): calls.append("h1")
        async def h2(e): calls.append("h2")

        bus.subscribe("CaseCreated", h1)
        bus.subscribe("CaseCreated", h2)
        await bus.publish(CaseCreated())

        assert "h1" in calls and "h2" in calls
