"""
API para el Event Store del sistema.
Permite consultar, buscar y analizar eventos del Panel IDM.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.security import verify_auth

router = APIRouter(prefix="/events", dependencies=[Depends(verify_auth)])


# NOTA (Ciclo 45): el antiguo modelo `EventQuery` se eliminó. Era código muerto
# —nunca instanciado por el endpoint ni por FastAPI— que declaraba un filtro
# `subcategory` que `GET /api/v1/events` no cableaba: documentaba un contrato que
# la capa de destino no honraba. El contrato de query real es la firma de
# `list_events` (de ahí sale el OpenAPI). Se evita mantener un modelo paralelo
# que vuelva a divergir del endpoint.


class EventCreate(BaseModel):
    """Crear un nuevo evento.

    `source` admite cualquier string para permitir SDK externos custom,
    pero los valores canónicos del ecosistema Micelia son los **6 sources
    oficiales** (5 dominios funcionales + el propio orquestador):

      - `"biohack"` — dominio salud
      - `"canela"` — dominio investigación
      - `"ideacursi"` — dominio educación
      - `"cybertools"` — dominio seguridad
      - `"auto-mat-ion"` — dominio automatización
      - `"micelia"` — orquestador (eventos internos del sistema)

    El source legacy `"idm-core"` (anterior al rebrand v0.1) se acepta con
    `DeprecationWarning` y se normaliza a `"micelia"` antes de persistir.
    Removible en v0.2.
    """
    category: str = Field(
        ..., description="Categoría funcional del evento (health, education, "
        "research, security, system, identity).",
    )
    subcategory: Optional[str] = Field(
        default=None, description="Subcategoría opcional dentro de la categoría.",
    )
    source: str = Field(
        ...,
        description=(
            "Origen del evento. Sources canónicos: 'biohack', 'canela', "
            "'ideacursi', 'cybertools', 'auto-mat-ion', 'micelia'. "
            "Valor legacy 'idm-core' aceptado con DeprecationWarning."
        ),
        examples=["biohack", "micelia"],
    )
    action: str = Field(
        ..., description="Acción realizada (create, update, delete, query, analyze).",
    )
    event_type: str = Field(
        ..., description="Tipo específico del evento, formato 'dominio.objeto.accion'.",
    )
    payload: dict = Field(default_factory=dict, description="Datos del evento.")
    metadata: dict = Field(default_factory=dict, description="Metadatos adicionales.")
    tags: List[str] = Field(default_factory=list, description="Etiquetas opcionales.")
    correlation_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Correlaciona eventos de un mismo flujo de trabajo. Opcional: los SDK "
            "de dominio biohack/cybertools lo emiten vía `publish_event(..., "
            "correlation_id=...)` (`VitalEvent.to_dict()`); canela/codking/auto-mat-ion "
            "no lo mandan. El EventStore lo persiste indexado y `GET /events/"
            "by-correlation/{id}` lo consulta — sin este campo se perdía en el ingest "
            "(Pydantic extra='ignore') y la traza quedaba siempre vacía (DP-8 / Ciclo 43)."
        ),
    )


class EventCreateResponse(BaseModel):
    """Respuesta de `POST /api/v1/events`.

    Contrato de SALIDA que consumen los SDK de dominio (auditado en Ciclo 44):
      - **biohack** y **cybertools** (`vital_sdk/client.py::publish_event`) leen
        `data.get("event_id")` cuando `status_code in (200, 201)` y devuelven ese
        id a su llamador → **`event_id` es el único campo que consumen**.
      - **canela** y **codking** (`vital_sdk/client.py::publish_event`) hacen
        `resp.raise_for_status()` (aceptan cualquier 2xx) y devuelven el dict
        completo → no dependen de campos concretos, pero sí del shape.
      - **auto-mat-ion** publica por Redis, no por REST → fuera de este contrato.

    Declarar el `response_model` fija el shape en runtime (FastAPI serializa y
    descarta claves extra) y lo publica en el OpenAPI, alineado con el mock e2e
    `tests/e2e/mocks/contracts.py::EventCreated`. Antes el endpoint devolvía un
    dict sin tipar: mismo antipatrón que Ciclos 42–43 (un contrato conocido que
    la capa de destino —aquí el `response_model`— no enforzaba).
    """

    event_id: UUID = Field(
        ..., description="ID del evento persistido (UUID). Lo consumen biohack/cybertools."
    )
    status: Literal["created"] = Field(
        default="created", description="Estado de la operación; siempre 'created'."
    )
    timestamp: datetime = Field(
        ..., description="Instante UTC de creación (ISO 8601)."
    )


@router.get("")
async def list_events(
    request: Request,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    source: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0
):
    """
    Lista eventos con filtros opcionales.

    La firma de este endpoint ES el contrato de query publicado en el OpenAPI
    (FastAPI genera el esquema desde los parámetros, no desde ningún modelo
    aparte). Filtros soportados 1:1 por `EventStore.query_events`:
    `category, subcategory, source, event_type, since, until, limit, offset`.
    `subcategory` se cableó en Ciclo 45: el store ya lo filtraba
    (`store.py::query_events`) y `_event_to_dict` lo serializa, pero el endpoint
    lo descartaba en silencio → era imposible filtrar por subcategoría vía REST
    pese a estar soportado de punta a punta (mismo antipatrón que Ciclos 43–44).
    """
    event_store = request.app.state.event_store

    if not event_store:
        raise HTTPException(status_code=503, detail="Event store not available")

    events = await event_store.query_events(
        category=category,
        subcategory=subcategory,
        source=source,
        event_type=event_type,
        since=since,
        until=until,
        limit=limit,
        offset=offset
    )

    return {
        "events": events,
        "count": len(events),
        "limit": limit,
        "offset": offset
    }


@router.get("/timeline/{date}")
async def get_timeline(
    request: Request,
    date: str,
    categories: Optional[str] = None
):
    """
    Obtiene timeline de eventos de un día específico.
    Formato de fecha: YYYY-MM-DD
    """
    event_store = request.app.state.event_store

    if not event_store:
        raise HTTPException(status_code=503, detail="Event store not available")

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    category_list = categories.split(",") if categories else None

    events = await event_store.get_timeline(
        date=target_date,
        categories=category_list
    )

    return {
        "date": date,
        "events": events,
        "count": len(events)
    }


@router.get("/by-correlation/{correlation_id}")
async def get_by_correlation(
    request: Request,
    correlation_id: UUID
):
    """
    Obtiene todos los eventos relacionados por correlation_id.
    Útil para rastrear flujos de trabajo completos.
    """
    event_store = request.app.state.event_store

    if not event_store:
        raise HTTPException(status_code=503, detail="Event store not available")

    events = await event_store.get_by_correlation(correlation_id)

    return {
        "correlation_id": str(correlation_id),
        "events": events,
        "count": len(events)
    }


@router.post("", response_model=EventCreateResponse)
async def create_event(
    request: Request,
    event: EventCreate
):
    """
    Crea un nuevo evento en el store.
    """
    event_store = request.app.state.event_store

    if not event_store:
        raise HTTPException(status_code=503, detail="Event store not available")

    event_id = await event_store.append_event(
        category=event.category,
        subcategory=event.subcategory,
        source=event.source,
        action=event.action,
        event_type=event.event_type,
        payload=event.payload,
        event_metadata=event.metadata,
        tags=event.tags,
        correlation_id=event.correlation_id,
    )

    return {
        "event_id": str(event_id),
        "status": "created",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/stats")
async def get_event_stats(
    request: Request,
    days: int = 7
):
    """
    Estadísticas de eventos de los últimos N días.
    """
    event_store = request.app.state.event_store

    if not event_store:
        raise HTTPException(status_code=503, detail="Event store not available")

    since = datetime.now(timezone.utc) - timedelta(days=days)

    stats = await event_store.get_stats(since=since)

    return {
        "period_days": days,
        "since": since.isoformat(),
        "stats": stats
    }


@router.get("/categories")
async def list_categories(request: Request):
    """
    Lista todas las categorías de eventos disponibles.
    """
    return {
        "categories": [
            {
                "name": "health",
                "description": "Eventos de salud (HealthKit, biomarcadores)",
                "subcategories": ["vitals", "sleep", "activity", "nutrition", "medication", "ml"]
            },
            {
                "name": "education",
                "description": "Eventos de educación (cursos, quizzes, papers)",
                "subcategories": ["learning", "sr", "research", "knowledge", "gamification", "protocol"]
            },
            {
                "name": "identity",
                "description": "Eventos de identidad (contactos, productividad)",
                "subcategories": ["profile", "social", "productivity", "patterns", "privacy"]
            },
            {
                "name": "system",
                "description": "Eventos del sistema (sync, compute, energy)",
                "subcategories": ["sync", "compute", "energy", "osascript"]
            }
        ]
    }
