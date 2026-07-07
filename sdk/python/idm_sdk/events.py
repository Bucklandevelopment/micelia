"""Event helpers, types, and category constants for the IDM event system."""

from typing import Optional


class EventCategory:
    """Well-known event categories matching Micelia's event store."""

    HEALTH = "health"
    EDUCATION = "education"
    IDENTITY = "identity"
    SECURITY = "security"
    SYSTEM = "system"


class EventBusChannel:
    """Redis Pub/Sub channel names used by Micelia's EventBus."""

    HEALTH = "idm.health"
    EDUCATION = "idm.education"
    IDENTITY = "idm.identity"
    SECURITY = "idm.security"
    SYSTEM = "idm.system"
    AI = "idm.ai"
    ENERGY = "idm.energy"

    @staticmethod
    def for_category(category: str) -> str:
        """Return the Redis channel name for a given category."""
        return f"idm.{category}"


def create_event(
    category: str,
    action: str,
    source: str,
    event_type: str = "sdk",
    payload: Optional[dict] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
    subcategory: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> dict:
    """Build an event dict matching Micelia's ``EventCreate`` schema.

    If ``correlation_id`` is provided it is included in the ``metadata``
    dict so that Micelia's event store can persist it for later
    correlation queries.

    Returns a dict ready to POST to ``/api/v1/events``.
    """
    meta = dict(metadata) if metadata else {}
    if correlation_id is not None:
        meta["correlation_id"] = correlation_id

    return {
        "category": category,
        "subcategory": subcategory,
        "source": source,
        "action": action,
        "event_type": event_type,
        "payload": payload or {},
        "metadata": meta,
        "tags": tags or [],
    }
