"""
E2E tests para la política de source-id (T1.4).

Verifica:
  a) source="micelia" (nuevo source del orquestador) se acepta y persiste.
  b) Los 5 dominios funcionales (biohack, canela, ideacursi, cybertools,
     auto-mat-ion) siguen funcionando como source válido.
  c) source="idm-core" (legacy) emite DeprecationWarning y se normaliza
     a "micelia" antes de persistir.

Decisión documentada en docs/REBRAND_MICELIA.md §4.
"""

from __future__ import annotations

import warnings
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.events.store import EventStore

pytestmark = pytest.mark.asyncio


FUNCTIONAL_DOMAINS = [
    "biohack",
    "canela",
    "ideacursi",
    "cybertools",
    "auto-mat-ion",
]


def _make_mock_event_store() -> AsyncMock:
    """
    Crea un mock del EventStore que captura la última llamada a
    append_event y devuelve un UUID, como el store real.
    """
    store = AsyncMock()
    store.append_event = AsyncMock(return_value=uuid4())
    return store


@pytest.fixture()
async def event_client(test_app, auth_headers):
    """
    Cliente HTTPX con un event_store mockeado inyectado en app.state.
    Restaura el estado original al finalizar.
    """
    original_store = test_app.state.event_store
    mock_store = _make_mock_event_store()
    test_app.state.event_store = mock_store

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as ac:
        yield ac, mock_store

    test_app.state.event_store = original_store


def _payload(source: str) -> dict:
    return {
        "category": "system",
        "source": source,
        "action": "create",
        "event_type": "test.source_id",
        "payload": {"note": f"source={source}"},
    }


async def test_micelia_source_accepted(event_client, auth_headers):
    """a) POST con source='micelia' devuelve 200/201 y llega al store."""
    client, mock_store = event_client

    resp = await client.post(
        "/api/v1/events",
        json=_payload("micelia"),
        headers=auth_headers,
    )

    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert body["status"] == "created"
    assert "event_id" in body

    mock_store.append_event.assert_awaited_once()
    call_kwargs = mock_store.append_event.await_args.kwargs
    assert call_kwargs["source"] == "micelia"


@pytest.mark.parametrize("domain", FUNCTIONAL_DOMAINS)
async def test_functional_domains_accepted(event_client, auth_headers, domain):
    """b) Los 5 dominios funcionales siguen aceptándose tal cual."""
    client, mock_store = event_client

    resp = await client.post(
        "/api/v1/events",
        json=_payload(domain),
        headers=auth_headers,
    )

    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["status"] == "created"

    mock_store.append_event.assert_awaited_once()
    assert mock_store.append_event.await_args.kwargs["source"] == domain


async def test_legacy_idm_core_normalized_with_deprecation(
    event_client, auth_headers, monkeypatch
):
    """
    c) source='idm-core' (legacy) emite DeprecationWarning Y se normaliza
    a 'micelia' antes de persistir.

    Endurecido tras T5.2: en lugar de capturar excepción genérica del INSERT,
    mockeamos la sesión de SQLAlchemy para interceptar el modelo que se va
    a persistir y validar que su atributo `source` ya es "micelia".
    """
    client, mock_store = event_client

    # 1) El endpoint sigue respondiendo con éxito (la lógica de normalización
    #    vive en el método append_event del store real; el endpoint sólo
    #    delega).
    resp = await client.post(
        "/api/v1/events",
        json=_payload("idm-core"),
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["status"] == "created"

    # 2) Verificamos directamente sobre EventStore.append_event que:
    #    (a) emite DeprecationWarning para 'idm-core'
    #    (b) persiste el modelo con source="micelia" (no "idm-core")
    #
    # Mockeamos `async_session` para capturar la instancia añadida sin
    # tocar BD. Esto es más estricto que el patrón try/except anterior:
    # ahora validamos el DATO que se persiste, no sólo el warning.
    from unittest.mock import MagicMock

    captured = {}

    class _FakeSession:
        """Captura el modelo añadido y simula commit/refresh sin BD."""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        def add(self, model):
            captured["model"] = model

        async def commit(self):
            return None

        async def refresh(self, model):
            return None

    store = EventStore()
    store.async_session = MagicMock(return_value=_FakeSession())

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        await store.append_event(
            category="system",
            source="idm-core",
            action="create",
            event_type="test.source_id.legacy",
        )

    # (a) DeprecationWarning emitida con mensaje claro
    deprecations = [
        w for w in caught if issubclass(w.category, DeprecationWarning)
    ]
    assert deprecations, "Se esperaba un DeprecationWarning para 'idm-core'"
    msg = str(deprecations[0].message)
    assert "idm-core" in msg
    assert "micelia" in msg

    # (b) El modelo persistido tiene source="micelia" (NO "idm-core")
    assert "model" in captured, "EventStore no llamó a session.add"
    assert captured["model"].source == "micelia", (
        f"source no se normalizó: persistió '{captured['model'].source}' "
        f"en lugar de 'micelia'"
    )
