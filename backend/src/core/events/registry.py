from backend.src.core.events.bus import get_event_bus


def register_all_handlers() -> None:
    """
    Register all event handlers here.
    Called once at application startup (lifespan).
    Handlers for each phase are added as they are implemented.
    """
    bus = get_event_bus()
    # Phase 7: Notifications, Audit, Automation handlers will be registered here
    _ = bus  # placeholder until handlers are added
