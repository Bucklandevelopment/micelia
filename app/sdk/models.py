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

# Map of category -> Redis pub/sub channel.
#
# FUENTE ÚNICA de los canales públicos del ecosistema: `EventBus.CHANNELS`
# (app/services/event_bus.py) se construye a partir de este mapa, de modo que la
# runtime del orquestador y este contrato del SDK no puedan derivar (invariante
# cubierta por tests/test_idm_sdk.py::test_eventbus_channels_derive_from_sdk).
#
# DRIFT INTER-PROYECTO CONOCIDO (ver DP-7 en docs/ITERATION_LOG.md 2026-07-13,
# Ciclo 41): el orquestador usa el prefijo `idm.*` mientras que los 5 SDK de
# dominio vendorizados (biohack, canela, cybertools, codking, auto-mat-ion)
# publican/suscriben en `vital.*` (herencia de la era vital-core). El destino del
# rebrand es `micelia.*`, que hoy no usa NADIE. Elegir el namespace canónico es
# una migración coordinada de los 6 servicios (irreversible) → DECISIÓN PENDIENTE,
# no se toca aquí de forma unilateral. Hoy el drift es LATENTE: Micelia no se
# suscribe a canales de dominio en código (solo publica `idm.prompts` interno y
# consume eventos de dominio por el Event Store REST, donde los source-id sí
# coinciden), pero cualquier consumo pub/sub cruzado fallaría en silencio.
EVENT_CHANNELS = {
    "health": "idm.health",
    "education": "idm.education",
    "identity": "idm.identity",
    "security": "idm.security",
    "system": "idm.system",
    "ai": "idm.ai",
    "energy": "idm.energy",
}
