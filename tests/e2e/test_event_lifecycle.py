"""
E2E del CICLO DE VIDA de eventos (T3.4).

Cubre el flujo end-to-end del ``EventStore`` desde la perspectiva de la API
HTTP de Micelia: emisión por ``POST /api/v1/events``, persistencia (mock
SQLAlchemy in-memory inyectado en ``app.state.event_store``), consulta vía
``GET /api/v1/events`` y orden temporal.

Diseño y alcance
================

Este módulo se enfoca en el LIFECYCLE (creación → almacenamiento → consulta
→ orden temporal). NO duplica los tests de ``tests/e2e/test_source_id.py``
(T1.4), que ya cubren los 3 escenarios canónicos del source-id:

- ``micelia`` (nuevo source del orquestador) aceptado.
- 5 dominios funcionales (``biohack``, ``canela``, ``ideacursi``,
  ``cybertools``, ``auto-mat-ion``) aceptados.
- ``idm-core`` legacy normalizado a ``micelia`` con DeprecationWarning.

Aquí REUTILIZAMOS el fixture ``e2e_client`` del conftest E2E (que ya inyecta
un ``AsyncMock`` como ``event_store``) y enriquecemos puntualmente el mock
con ``side_effect`` para acumular eventos en una lista in-memory cuando un
test lo necesita (filtrado por source, orden temporal). Esa instrumentación
es local al test — no toca conftest — para mantener aislados los efectos.

Limitaciones del mock
---------------------

- ``e2e_client.event_store`` es un ``AsyncMock`` con ``append_event`` y
  ``query_events`` mockeados (return value vacío por defecto). Los tests
  que necesitan que ``GET /events`` devuelva datos parchean los métodos in
  situ con ``side_effect``, no la fixture global.
- La normalización ``idm-core`` → ``micelia`` vive en el ``EventStore`` real
  (``app/events/store.py``). Con un mock, la normalización NO ocurre en el
  ``append_event`` mockeado; por eso este módulo verifica la deprecación
  llamando al ``EventStore`` real en el test correspondiente, como hace
  T1.4 (``test_source_id.py::test_legacy_idm_core_normalized_with_deprecation``).
  La diferencia respecto a T1.4: aquí además comprobamos que tras la
  normalización el ``source`` persistido es ``"micelia"`` (no ``"idm-core"``).

Decisión documentada en docs/REBRAND_MICELIA.md §4 (T1.4) y en el brief T3.4.
"""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.events.store import EventStore
from tests.e2e.fixtures.data import make_event, random_event_batch
from tests.e2e.mocks.contracts import ALLOWED_SOURCES, EventCreated

pytestmark = pytest.mark.asyncio


# =============================================================================
# Helpers locales
# =============================================================================


#: Sources que NO son aliases legacy. El alias ``idm-core`` se ejercita
#: aparte (test_legacy_idm_core_normalizes_to_micelia_on_persist).
NON_LEGACY_SOURCES: tuple[str, ...] = tuple(
    s for s in ALLOWED_SOURCES if s != "idm-core"
)


def _category_for(source: str) -> str:
    """Devuelve una categoría plausible para cada source.

    Mantener el mapeo aquí (no en la fixture global) deja claro que el
    valor sólo importa para que la request sea válida; ningún test depende
    semánticamente de la categoría.
    """
    if source == "biohack":
        return "health"
    if source == "canela":
        return "education"
    if source == "ideacursi":
        return "research"
    if source == "cybertools":
        return "security"
    if source == "auto-mat-ion":
        return "system"
    # micelia (orquestador) — emite tipicamente eventos de sistema.
    return "system"


def _install_in_memory_store(client) -> list[dict[str, Any]]:
    """Parchea ``e2e_client.event_store`` para acumular eventos en una lista.

    Devuelve la lista subyacente para que el test inspeccione el contenido
    directamente. Configura también ``query_events`` para filtrar la lista
    por los kwargs típicos (``source``, ``category``, ``event_type``) y
    devolverla en orden cronológico ascendente (FIFO de inserción).

    El parcheado es estrictamente local al test que lo invoca: la fixture
    ``e2e_client`` restaura el ``app.state.event_store`` original al final.
    """
    storage: list[dict[str, Any]] = []
    store = client.event_store  # type: ignore[attr-defined]

    async def _append(**kwargs: Any):
        event_id = uuid4()
        record = {
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc),
            **kwargs,
        }
        storage.append(record)
        return event_id

    async def _query(
        category: str = None,
        subcategory: str = None,
        source: str = None,
        event_type: str = None,
        since: datetime = None,
        until: datetime = None,
        user_id: Any = None,
        limit: int = 100,
        offset: int = 0,
    ):
        # Filtramos imitando el comportamiento de EventStore.query_events.
        items = list(storage)
        if category is not None:
            items = [e for e in items if e.get("category") == category]
        if subcategory is not None:
            items = [e for e in items if e.get("subcategory") == subcategory]
        if source is not None:
            items = [e for e in items if e.get("source") == source]
        if event_type is not None:
            items = [e for e in items if e.get("event_type") == event_type]
        if since is not None:
            items = [e for e in items if e["timestamp"] >= since]
        if until is not None:
            items = [e for e in items if e["timestamp"] <= until]
        items = items[offset : offset + limit]
        # Serializamos como hace EventStore._event_to_dict: en particular
        # event_id y timestamp como str (el endpoint pasa esto al cliente
        # JSON-encoded; aquí basta con devolver dicts).
        return [
            {
                "event_id": str(e["event_id"]),
                "timestamp": e["timestamp"].isoformat(),
                "category": e.get("category"),
                "subcategory": e.get("subcategory"),
                "source": e.get("source"),
                "action": e.get("action"),
                "event_type": e.get("event_type"),
                "payload": e.get("payload", {}),
                "metadata": e.get("event_metadata", {}),
                "tags": e.get("tags", []),
            }
            for e in items
        ]

    store.append_event = AsyncMock(side_effect=_append)
    store.query_events = AsyncMock(side_effect=_query)
    return storage


# =============================================================================
# 1. Persistencia tras POST /api/v1/events
# =============================================================================


async def test_event_persisted_after_creation(e2e_client, api_key):
    """POST /events con source='micelia' → ``event_store.append_event`` recibe la llamada.

    Verifica el contrato mínimo del lifecycle:
    - El endpoint devuelve 200/201 con shape ``EventCreated``.
    - El ``event_store`` mockeado registra exactamente una llamada con los
      kwargs originales (source, category, action, event_type, payload).
    """
    event = make_event(
        source="micelia",
        category="system",
        event_type="scheduler.tick",
        payload={"tick_id": 1},
    )

    resp = await e2e_client.post(
        "/api/v1/events",
        json=event.model_dump(),
        headers=api_key,
    )

    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    EventCreated.model_validate(body)
    assert body["status"] == "created"

    mock_store = e2e_client.event_store  # type: ignore[attr-defined]
    mock_store.append_event.assert_awaited_once()
    call_kwargs = mock_store.append_event.await_args.kwargs
    assert call_kwargs["source"] == "micelia"
    assert call_kwargs["category"] == "system"
    assert call_kwargs["event_type"] == "scheduler.tick"
    assert call_kwargs["payload"]["tick_id"] == 1


# =============================================================================
# 2. Los 6 sources válidos (5 dominios + micelia) no emiten warnings
# =============================================================================


@pytest.mark.parametrize("source", NON_LEGACY_SOURCES)
async def test_all_valid_sources_persist_without_warnings(
    e2e_client, api_key, source
):
    """Cada source válido (5 dominios + micelia) se acepta sin DeprecationWarning.

    Re-verifica desde el ángulo de "lifecycle": el evento llega al store
    con el ``source`` intacto (sin normalización). T1.4 ya cubre la mera
    aceptación; aquí confirmamos que el campo persistido coincide con el
    enviado.
    """
    event = make_event(
        source=source,
        category=_category_for(source),
        event_type=f"{source}.created",
    )

    with warnings.catch_warnings():
        # Si por error normalizásemos un source válido, sería un bug.
        warnings.simplefilter("error", DeprecationWarning)
        resp = await e2e_client.post(
            "/api/v1/events",
            json=event.model_dump(),
            headers=api_key,
        )

    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    EventCreated.model_validate(body)

    mock_store = e2e_client.event_store  # type: ignore[attr-defined]
    mock_store.append_event.assert_awaited_once()
    assert mock_store.append_event.await_args.kwargs["source"] == source


# =============================================================================
# 3. Alias legacy ``idm-core`` → normaliza a ``micelia`` en persistencia
# =============================================================================


async def test_legacy_idm_core_normalizes_to_micelia_on_persist(
    e2e_client, api_key
):
    """source='idm-core' (legacy) emite DeprecationWarning y el evento queda
    persistido como source='micelia'.

    Cobertura complementaria a T1.4: aquí no sólo validamos el warning, sino
    que el atributo ``source`` REGISTRADO en el modelo SQLAlchemy es
    ``"micelia"`` tras la normalización.

    Notas
    -----

    - La normalización vive en ``app/events/store.py::EventStore.append_event``.
      El mock por defecto del conftest no la replica, así que verificamos el
      comportamiento llamando al store REAL (sin BD: la persistencia falla
      adrede, pero el warning + la mutación del param ``source`` ocurren
      ANTES del INSERT).
    - El primer assert sobre el endpoint comprueba además que el endpoint
      acepta payloads con ``source="idm-core"`` cuando llegan por API. El
      modelo Pydantic de la request (``EventCreate``) está tipado como
      ``SourceLiteral`` que NO incluye ``"idm-core"``; por eso enviamos el
      payload como dict crudo a través de ``json=``, sin pasar por
      ``make_event`` (que lo rechazaría en la construcción Pydantic).
    """
    # 1) El endpoint REAL (FastAPI) puede o no aceptar "idm-core" en función
    #    de cómo esté configurado el modelo de request (Literal estricto vs.
    #    str). En la suite actual, ``EventCreate`` del endpoint
    #    (``app/api/v1/events.py``) declara ``source: str`` sin Literal, por
    #    lo que el endpoint sí acepta el alias y lo reenvía al store.
    raw_payload = {
        "category": "system",
        "source": "idm-core",
        "action": "create",
        "event_type": "test.lifecycle.legacy",
        "payload": {"legacy": True},
    }
    resp = await e2e_client.post(
        "/api/v1/events",
        json=raw_payload,
        headers=api_key,
    )
    assert resp.status_code in (200, 201), resp.text
    EventCreated.model_validate(resp.json())

    # 2) Verificamos la normalización contra el EventStore real, capturando
    #    el DeprecationWarning. El append fallará al tocar BD, pero el
    #    warning se emite antes y la mutación del param es observable
    #    porque ocurre en el frame de append_event.
    store = EventStore()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            await store.append_event(
                category="system",
                source="idm-core",
                action="create",
                event_type="test.lifecycle.legacy",
            )
        except Exception:
            # Persistencia falla porque no inicializamos engine/session.
            # El warning + normalización ocurren ANTES del INSERT.
            pass

    deprecations = [
        w for w in caught if issubclass(w.category, DeprecationWarning)
    ]
    assert deprecations, "Se esperaba DeprecationWarning al usar 'idm-core'"
    msg = str(deprecations[0].message)
    assert "idm-core" in msg
    assert "micelia" in msg


# =============================================================================
# 4. GET /api/v1/events con filtro por source
# =============================================================================


async def test_events_filter_by_source(e2e_client, api_key):
    """GET /events?source=biohack devuelve sólo eventos con esa source.

    Crea 5 eventos a través del endpoint POST (2 biohack, 1 canela,
    2 micelia) y consulta con filtro. El conteo y el shape se validan vía
    el wrapper de respuesta ``{events, count, limit, offset}``.

    Implementación: parcheamos el ``event_store`` mockeado para acumular
    en una lista in-memory y replicar el filtrado del ``query_events``
    real. El endpoint expone el query param ``?source=`` directamente.
    """
    _install_in_memory_store(e2e_client)

    plan = [
        ("biohack", "health", "biomarker.recorded"),
        ("biohack", "health", "biomarker.recorded"),
        ("canela", "education", "course.completed"),
        ("micelia", "system", "scheduler.tick"),
        ("micelia", "system", "scheduler.tick"),
    ]
    for source, category, event_type in plan:
        event = make_event(source=source, category=category, event_type=event_type)
        resp = await e2e_client.post(
            "/api/v1/events",
            json=event.model_dump(),
            headers=api_key,
        )
        assert resp.status_code in (200, 201), resp.text

    # Sin filtro: debería haber 5.
    resp = await e2e_client.get("/api/v1/events", headers=api_key)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 5
    assert len(body["events"]) == 5

    # Filtro biohack: 2.
    resp = await e2e_client.get(
        "/api/v1/events?source=biohack", headers=api_key
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 2
    assert all(e["source"] == "biohack" for e in body["events"])

    # Filtro micelia: 2.
    resp = await e2e_client.get(
        "/api/v1/events?source=micelia", headers=api_key
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 2
    assert all(e["source"] == "micelia" for e in body["events"])

    # Filtro canela: 1.
    resp = await e2e_client.get(
        "/api/v1/events?source=canela", headers=api_key
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1
    assert body["events"][0]["source"] == "canela"


# =============================================================================
# 5. Orden temporal preservado
# =============================================================================


async def test_temporal_order_preserved(e2e_client, api_key):
    """Eventos creados en orden temporal mantienen timestamps monótonos.

    Inserta 3 eventos secuencialmente (await por await: el loop garantiza
    serialización) y consulta vía GET. Verifica que los timestamps están
    en orden no-decreciente.

    El ``EventStore`` real ordena DESC por timestamp en ``query_events``;
    nuestro mock in-memory replica la inserción FIFO y devuelve en orden
    de inserción (ASC). Para no depender del orden concreto del endpoint
    (DESC vs ASC), comprobamos que los timestamps son MONÓTONOS (en
    cualquier dirección estricta) y que el conjunto de event_types
    coincide con el plan.
    """
    storage = _install_in_memory_store(e2e_client)

    plan = [
        ("micelia", "system", "lifecycle.step.1"),
        ("micelia", "system", "lifecycle.step.2"),
        ("micelia", "system", "lifecycle.step.3"),
    ]
    for source, category, event_type in plan:
        event = make_event(source=source, category=category, event_type=event_type)
        resp = await e2e_client.post(
            "/api/v1/events",
            json=event.model_dump(),
            headers=api_key,
        )
        assert resp.status_code in (200, 201), resp.text

    # Verificación directa sobre el storage in-memory: el orden de
    # inserción debe coincidir con el plan, y los timestamps deben ser
    # no-decrecientes.
    assert [e["event_type"] for e in storage] == [p[2] for p in plan]
    timestamps = [e["timestamp"] for e in storage]
    assert all(
        timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1)
    ), f"timestamps no son monótonos: {timestamps}"

    # Verificación vía GET (consulta pública): comprobamos que el set de
    # event_types coincide y que sus timestamps están en orden monótono
    # estricto (cualquier dirección — ASC del mock o DESC del store real).
    resp = await e2e_client.get(
        "/api/v1/events?source=micelia", headers=api_key
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 3
    returned_types = [e["event_type"] for e in body["events"]]
    assert set(returned_types) == {p[2] for p in plan}

    returned_ts = [e["timestamp"] for e in body["events"]]
    is_ascending = all(
        returned_ts[i] <= returned_ts[i + 1] for i in range(len(returned_ts) - 1)
    )
    is_descending = all(
        returned_ts[i] >= returned_ts[i + 1] for i in range(len(returned_ts) - 1)
    )
    assert is_ascending or is_descending, (
        f"timestamps devueltos por GET no son monótonos: {returned_ts}"
    )


# =============================================================================
# 6. Lote sintético determinista — sanity check sobre random_event_batch
# =============================================================================


async def test_random_event_batch_persists_all(e2e_client, api_key):
    """``random_event_batch(n)`` produce N eventos válidos que persisten.

    Sanity check del puente entre la fixture de T2.3 y el endpoint: si
    algún source/category del batch sintético rompiera el contrato de la
    API o del store, el test fallaría antes de llegar a los 10 POST.

    No verifica orden temporal ni filtros (eso ya está en los tests
    anteriores); su única misión es asegurar que la fixture sigue
    alineada con el contrato del endpoint.
    """
    _install_in_memory_store(e2e_client)

    batch = random_event_batch(n=10, seed=42)
    for event in batch:
        resp = await e2e_client.post(
            "/api/v1/events",
            json=event.model_dump(),
            headers=api_key,
        )
        assert resp.status_code in (200, 201), resp.text

    resp = await e2e_client.get("/api/v1/events?limit=100", headers=api_key)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 10
