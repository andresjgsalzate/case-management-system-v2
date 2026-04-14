from backend.src.core.events.bus import get_event_bus


def register_all_handlers() -> None:
    """
    Register all event handlers here.
    Called once at application startup (lifespan).
    """
    bus = get_event_bus()

    from backend.src.modules.activity.application.handlers import (
        register_handlers as activity_handlers,
    )
    activity_handlers(bus)

    from backend.src.modules.classification.application.handlers import (
        register_handlers as classification_handlers,
    )
    classification_handlers(bus)

    from backend.src.modules.sla.application.handlers import (
        register_handlers as sla_handlers,
    )
    sla_handlers(bus)

    from backend.src.modules.automation.application.handler import register_automation_handler
    register_automation_handler(bus)

    from backend.src.modules.notifications.application.handlers import (
        register_handlers as notification_handlers,
    )
    notification_handlers(bus)
