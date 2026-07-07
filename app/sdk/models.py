"""
Data models for the Micelia SDK.

Defines the standardized contracts for health checks and events
that all microservices must follow.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HealthResponse:
    """
    Standardized health check response that every microservice must return.

    Usage:
        @app.get("/health")
        def health():
            return client.health_response(
                dependencies={"postgresql": "healthy", "redis": "healthy"}
            )
    """
    status: str  # "healthy", "degraded", "unhealthy"
    version: str
    service: str
    category: str
    port: int
    capabilities: List[str]
    uptime_seconds: float
    dependencies: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IdmEvent:
    """
    Standardized event payload for the Micelia Event Store.

    Aligns with the EventCreate schema in app/api/v1/events.py.
    """
    category: str       # health, education, research, security, system
    source: str         # biohack, canela, ideacursi, cybertools, auto-mat-ion, micelia
    action: str         # create, update, delete, query, analyze
    event_type: str     # e.g. biomarker.recorded, paper.ingested, lesson.completed
    payload: Dict[str, Any] = field(default_factory=dict)
    subcategory: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    correlation_id: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # Remove None values for cleaner payloads
        return {k: v for k, v in d.items() if v is not None}


# Valid categories for events (aligned with EventBus channels)
VALID_CATEGORIES = {"health", "education", "research", "security", "system", "identity"}

# Map of category -> Redis pub/sub channel (aligned with EventBus.CHANNELS)
EVENT_CHANNELS = {
    "health": "idm.health",
    "education": "idm.education",
    "identity": "idm.identity",
    "security": "idm.security",
    "system": "idm.system",
    "ai": "idm.ai",
    "energy": "idm.energy",
}
