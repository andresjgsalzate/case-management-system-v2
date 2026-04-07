from backend.src.core.events.bus import get_event_bus


def register_all_handlers() -> None:
    """
    Register all event handlers here.
    Called once at application startup (lifespan).
    """
    bus = get_event_bus()
    from backend.src.modules.activity.application.handlers import register_handlers as activity_handlers
    activity_handlers(bus)
