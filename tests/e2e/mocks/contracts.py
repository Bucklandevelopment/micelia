"""
Pydantic v2 contracts entre Micelia y biohack-app (T2.1).

Estos modelos son la única fuente de verdad para:
- T2.2 (mock server in-process con respx): define las rutas usando estos
  modelos para validar payload de entrada y serializar las respuestas.
- T2.3 (datos sintéticos): construye fixtures que satisfacen estos contratos.
- T3.x (E2E): los tests pueden importar los modelos para validar respuestas.

Política estricta: todos los modelos usan `extra="forbid"` para detectar
drift entre lo documentado y lo que el mock devuelve. Si el código real de
biohack-app añade un campo, el test debe fallar primero y obligar a
actualizar el contrato.

Divergencias con el brief original de T2.1 están documentadas en
docs/MICELIA_BIOHACK_CONTRACT.md sección "Notas".
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Constantes compartidas
# =============================================================================

#: Source-id válidos para eventos. 5 dominios funcionales + el propio
#: orquestador (decisión T1.4). T2.2 importa esta tupla para validar en
#: runtime y para construir fixtures aleatorios.
ALLOWED_SOURCES: tuple[str, ...] = (
    "biohack",
    "canela",
    "ideacursi",
    "cybertools",
    "auto-mat-ion",
    "micelia",
)

SourceLiteral = Literal[
    "biohack", "canela", "ideacursi", "cybertools", "auto-mat-ion", "micelia"
]

CategoryLiteral = Literal[
    "health", "education", "research", "security", "system", "identity"
]

ActionLiteral = Literal["create", "update", "delete", "query", "analyze"]


class _StrictModel(BaseModel):
    """Base con `extra="forbid"`: cualquier campo no declarado rompe el test."""

    model_config = ConfigDict(extra="forbid")


# =============================================================================
# 1. HealthStatus — GET /api/v1/health  y  GET /api/v1/health/live
# =============================================================================


class HealthStatus(_StrictModel):
    """Respuesta de los health checks ligeros de biohack-app.

    Emisor: biohack-app. Consumidor: Micelia (gateway y service registry).
    `status` toma `"ok"` para `/health`, `"alive"` para `/health/live`.
    Los campos `service` y `version` son INFERRED — pending T0.1 validation.
    """

    status: Literal["ok", "alive", "degraded", "down"]
    timestamp: datetime
    service: Optional[str] = Field(
        default=None,
        description="INFERRED — pending T0.1 validation; nombre del servicio.",
    )
    version: Optional[str] = Field(
        default=None,
        description="INFERRED — pending T0.1 validation; versión del servicio.",
    )


class HealthReady(_StrictModel):
    """Respuesta de GET /api/v1/health/ready.

    Emisor: biohack-app. `status` es `"ready"` o `"not_ready"`; cuando es
    `"not_ready"`, `reason` describe la dependencia bloqueada.
    """

    status: Literal["ready", "not_ready"]
    timestamp: datetime
    reason: Optional[str] = None


# =============================================================================
# 2. HealthDetailed / HealthServices — endpoints de diagnóstico
# =============================================================================


class ServiceStatusEntry(_StrictModel):
    """Estado individual de una dependencia/servicio.

    Espejo de `app/api/v1/health.py:ServiceStatus`. biohack-app sigue la
    misma convención SDK que Micelia, así que reutilizamos la shape.
    INFERRED — pending T0.1 validation.
    """

    name: str
    url: str
    enabled: bool
    healthy: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthResources(_StrictModel):
    """Sub-bloque `resources` de /health/detailed.

    INFERRED — pending T0.1 validation.
    """

    cpu_percent: float
    memory: dict[str, float]
    disk: dict[str, float]


class HealthDetailed(_StrictModel):
    """Respuesta de GET /api/v1/health/detailed.

    Emisor: biohack-app. Consumidor: Micelia CLI (`app/cli.py:63`).
    Shape derivada de cómo Micelia la lee; INFERRED — pending T0.1.
    """

    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: datetime
    uptime_seconds: float
    services: dict[str, ServiceStatusEntry]
    resources: HealthResources


class HealthServicesResponse(_StrictModel):
    """Respuesta de GET /api/v1/health/services.

    Emisor: biohack-app (y, simétricamente, Micelia para su propio registry).
    Consumidor: Micelia CLI (`app/cli.py:123`) y `IdmServiceClient` (que
    biohack-app importa como `idm_sdk`) para descubrir peers.
    """

    services: dict[str, ServiceStatusEntry]


#: Alias semántico para la dirección biohack → Micelia (lo mismo de wire).
ServiceRegistryResponse = HealthServicesResponse


# =============================================================================
# 3. Bio-Savant chat — POST /api/v1/bio-savant/chat
# =============================================================================


class BioSavantSource(_StrictModel):
    """Cita devuelta por Bio-Savant.

    INFERRED — pending T0.1 validation.
    """

    title: str
    url: str
    confidence: float = Field(ge=0.0, le=1.0)


class BioSavantChatRequest(_StrictModel):
    """Request a /api/v1/bio-savant/chat.

    Emisor: Micelia (`app/api/v1/ai.py:255` envía `message` y `health_context`).
    `user_id` y `context_window` son INFERRED — pending T0.1; los marcamos
    opcionales para que el mock acepte clientes que ya los envíen.
    """

    message: str
    health_context: dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = Field(
        default=None,
        description="INFERRED — pending T0.1 validation.",
    )
    context_window: Optional[int] = Field(
        default=None,
        description="INFERRED — pending T0.1 validation; nº de turnos previos.",
    )


class BioSavantChatResponse(_StrictModel):
    """Respuesta de /api/v1/bio-savant/chat.

    Emisor: biohack-app. `reasoning_trace` opcional.
    INFERRED — pending T0.1 validation.
    """

    answer: str
    sources: list[BioSavantSource] = Field(default_factory=list)
    reasoning_trace: Optional[list[str]] = None


# =============================================================================
# 4. ML production predict — POST /api/v1/ml-production/predict
# =============================================================================


class MLPredictionRequest(_StrictModel):
    """Request a /api/v1/ml-production/predict.

    Emisor: Micelia (`app/api/v1/ai.py:265` envía hoy sólo `{"metrics": ...}`).
    `model_name` y `features` son la forma deseada por T2.3 y están INFERRED —
    pending T0.1 validation. Cualquiera de los dos sub-grupos puede venir.
    """

    metrics: Optional[dict[str, Any]] = Field(
        default=None,
        description="Forma observada en Micelia hoy (compatibilidad retro).",
    )
    model_name: Optional[str] = Field(
        default=None,
        description="INFERRED — pending T0.1 validation.",
    )
    features: Optional[dict[str, Any]] = Field(
        default=None,
        description="INFERRED — pending T0.1 validation.",
    )


class MLPredictionResponse(_StrictModel):
    """Respuesta de /api/v1/ml-production/predict.

    Emisor: biohack-app. INFERRED — pending T0.1 validation.
    """

    prediction: Any
    confidence: float = Field(ge=0.0, le=1.0)
    model_version: str


# =============================================================================
# 5. Biomarker series — GET /api/v1/biomarkers/series
# =============================================================================


class BiomarkerPoint(_StrictModel):
    """Un punto temporal de una serie de biomarker.

    INFERRED — pending T0.1 validation (endpoint no llamado hoy por Micelia,
    pero necesario para T2.3 y T3.1).
    """

    timestamp: datetime
    value: float


class BiomarkerSeries(_StrictModel):
    """Respuesta de /api/v1/biomarkers/series.

    Emisor: biohack-app. INFERRED — pending T0.1 validation.
    """

    user_id: str
    metric: str
    unit: str
    points: list[BiomarkerPoint] = Field(default_factory=list)


# =============================================================================
# 6. Events — POST /api/v1/events  (biohack → Micelia)
# =============================================================================


class EventCreate(_StrictModel):
    """Request a /api/v1/events.

    Emisor: cualquier dominio funcional o el propio Micelia, vía
    `IdmServiceClient.publish_event` (`app/sdk/client.py`).
    Consumidor: `app/api/v1/events.py:create_event`.

    El campo `source` se restringe a `ALLOWED_SOURCES` (5 dominios + micelia).
    """

    category: CategoryLiteral
    source: SourceLiteral
    action: ActionLiteral
    event_type: str
    subcategory: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    correlation_id: Optional[str] = None


class EventCreated(_StrictModel):
    """Respuesta de /api/v1/events.

    Emisor: Micelia. `status` es `"created"` (no `"accepted"` como sugería el
    brief — honramos el código real, `app/api/v1/events.py:create_event`).
    """

    event_id: UUID
    status: Literal["created"]
    timestamp: datetime


# =============================================================================
# 7. Auth validation — GET /api/v1/auth/me  (biohack → Micelia)
# =============================================================================


class ApiKeyValidation(_StrictModel):
    """Respuesta de /api/v1/auth/me.

    Emisor: Micelia (`app/api/v1/auth.py:get_current_user`). Acepta tanto
    `X-API-Key` como `Bearer JWT` vía `verify_auth`.

    Los campos `valid`, `permissions`, `rate_limit` que pedía el brief NO
    existen en el endpoint actual; quedan reservados (Optional) por si T0.1
    decide migrar a un `/auth/validate` dedicado. INFERRED — pending T0.1.
    """

    username: str
    auth_method: Literal["apikey", "jwt", "unknown"]
    auth_identity: str
    valid: Optional[bool] = Field(
        default=None,
        description="INFERRED — reservado para futuro /auth/validate.",
    )
    permissions: Optional[set[str]] = Field(
        default=None,
        description="INFERRED — reservado para futuro /auth/validate.",
    )
    rate_limit: Optional[int] = Field(
        default=None,
        description="INFERRED — reservado para futuro /auth/validate.",
    )


# =============================================================================
# 8. Service registry entry — GET /api/v1/health/services  (biohack → Micelia)
# =============================================================================


class ServiceRegistryEntry(_StrictModel):
    """Entrada individual del registry, vista por un cliente del SDK.

    Es el mismo wire format que `ServiceStatusEntry` pero la documentamos como
    modelo separado para claridad semántica desde el lado biohack→Micelia.
    Añade `last_check` opcional (INFERRED).
    """

    name: str
    url: str
    enabled: bool
    healthy: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    last_check: Optional[datetime] = Field(
        default=None,
        description="INFERRED — pending T0.1 validation.",
    )


# =============================================================================
# Re-exports convenientes para T2.2 / T2.3
# =============================================================================

__all__ = (
    "ALLOWED_SOURCES",
    "SourceLiteral",
    "CategoryLiteral",
    "ActionLiteral",
    # Health
    "HealthStatus",
    "HealthReady",
    "ServiceStatusEntry",
    "HealthResources",
    "HealthDetailed",
    "HealthServicesResponse",
    "ServiceRegistryResponse",
    # AI
    "BioSavantSource",
    "BioSavantChatRequest",
    "BioSavantChatResponse",
    "MLPredictionRequest",
    "MLPredictionResponse",
    # Biomarkers
    "BiomarkerPoint",
    "BiomarkerSeries",
    # Events
    "EventCreate",
    "EventCreated",
    # Auth / registry
    "ApiKeyValidation",
    "ServiceRegistryEntry",
)
