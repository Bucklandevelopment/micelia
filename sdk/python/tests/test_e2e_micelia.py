"""
E2E tests for the Python SDK (T3.5).

Verifica:
  1) `IdmClient` es un alias de `MiceliaClient` (mismo objeto).
  2) Crear un `IdmClient` no rompe (compat-API). Como el alias es a nivel de
     módulo sin warning automática, validamos sólo la identidad. La warning
     sí se prueba en (5) con el kwarg legacy `idm_core_url=` del
     `MiceliaServiceClient` (app-internal SDK, T1.3).
  3) `MiceliaClient` golpea el orquestador Micelia (FastAPI app de
     `tests/conftest.py`) vía ASGITransport y obtiene `health_check()` OK.
  4) Emitir un evento con `source="micelia"` devuelve 200/201 y persiste con
     ese source en el `event_store` (mockeado).
  5) Emitir un evento con `source="idm-core"` legacy: el endpoint sigue
     respondiendo OK y la normalización + DeprecationWarning ocurre en el
     `EventStore` real (verificado en `tests/e2e/test_source_id.py`); aquí
     comprobamos sólo el round-trip exitoso desde el SDK.
  6) `MiceliaServiceClient` (app-internal SDK) acepta `micelia_url=` y también
     el kwarg deprecated `idm_core_url=` con `DeprecationWarning`.

Nota: el SDK `MiceliaClient` toma `config: IdmConfig`, no `base_url=`. Para
inyectar el ASGI transport y dirigir la base_url al app de pruebas usamos
`monkeypatch` sobre `self._http`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

# Asegura que el SDK local sea importable y la app de Micelia también.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from idm_sdk import IdmClient, IdmConfig, MiceliaClient  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sdk_config() -> IdmConfig:
    return IdmConfig(
        core_url="http://micelia-test",
        api_key="test-api-key",
        service_name="biohack-app",
        service_port=8080,
        redis_url="redis://localhost:6379",
    )


@pytest.fixture()
def micelia_app():
    """
    Construye una FastAPI app equivalente a la de `tests/conftest.py`,
    con el `event_store` mockeado para capturar eventos emitidos por el SDK.
    """
    from unittest.mock import MagicMock

    from fastapi import FastAPI

    from app.api.v1 import ai, energy, events, frangels, gateway, health, system
    from app.api.v1.health import ServiceStatus

    app = FastAPI()

    mock_service_registry = MagicMock()
    mock_service_registry.check_service = AsyncMock(
        return_value=ServiceStatus(
            name="mock",
            url="http://mock:8080",
            enabled=True,
            healthy=True,
            latency_ms=1.0,
            error=None,
        )
    )

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {}
    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)
    mock_http_client.post = AsyncMock(return_value=mock_response)

    mock_event_store = AsyncMock()
    mock_event_store.append_event = AsyncMock(return_value=uuid4())

    app.state.http_client = mock_http_client
    app.state.service_registry = mock_service_registry
    app.state.event_bus = AsyncMock()
    app.state.event_store = mock_event_store

    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(gateway.router, prefix="/api/v1", tags=["Gateway"])
    app.include_router(events.router, prefix="/api/v1", tags=["Events"])
    app.include_router(ai.router, prefix="/api/v1", tags=["AI"])
    app.include_router(energy.router, prefix="/api/v1", tags=["Energy"])
    app.include_router(system.router, prefix="/api/v1", tags=["System"])
    app.include_router(frangels.router, prefix="/api/v1", tags=["Frangels"])

    return app


@pytest.fixture()
def micelia_api_key(micelia_app) -> str:
    """Genera (y registra) una API key válida para la app de pruebas."""
    from app.core.security import api_key_manager

    return api_key_manager.generate_key(
        name="sdk-e2e",
        permissions={"all"},
        rate_limit=10000,
    )


@pytest.fixture()
async def sdk_client_against_micelia(sdk_config, micelia_app, micelia_api_key):
    """
    MiceliaClient con su `_http` interno re-cableado a un AsyncClient
    que usa ASGITransport contra `micelia_app`. Esto permite hablar con
    la app real sin levantar un servidor.
    """
    transport = ASGITransport(app=micelia_app)
    asgi_http = AsyncClient(
        transport=transport,
        base_url="http://micelia-test",
        headers={"X-API-Key": micelia_api_key},
        timeout=httpx.Timeout(10.0),
    )

    client = MiceliaClient(sdk_config)
    # Reemplaza el httpx interno por uno apuntando a la app de tests.
    await client._http.aclose()
    client._http = asgi_http

    try:
        yield client, micelia_app
    finally:
        await asgi_http.aclose()


# ---------------------------------------------------------------------------
# 1) Alias IdmClient = MiceliaClient
# ---------------------------------------------------------------------------


def test_idm_client_is_subclass_of_micelia_client():
    """`IdmClient` es subclass de `MiceliaClient` (tras T5.4: ya no es alias
    de módulo sino una subclase que emite DeprecationWarning al instanciar).

    Esto preserva `isinstance(x, IdmClient)` y `isinstance(x, MiceliaClient)`
    para consumidores existentes.
    """
    assert issubclass(IdmClient, MiceliaClient)
    # IdmClient is NOT the same object anymore (post-T5.4); it's a subclass.
    assert IdmClient is not MiceliaClient


# ---------------------------------------------------------------------------
# 2) IdmClient emite DeprecationWarning al instanciarse (compat-API)
# ---------------------------------------------------------------------------


def test_idm_client_instantiation_emits_deprecation_warning(sdk_config):
    """
    Al construir `IdmClient(...)` el SDK debe emitir DeprecationWarning
    apuntando al uso de `MiceliaClient`. La instancia debe seguir siendo
    funcionalmente válida (isinstance de MiceliaClient).
    """
    with pytest.warns(DeprecationWarning, match=r"IdmClient.*deprecad|MiceliaClient"):
        client = IdmClient(sdk_config)
    assert isinstance(client, MiceliaClient)
    assert client.config.service_name == "biohack-app"


# ---------------------------------------------------------------------------
# 3) MiceliaClient golpea Micelia ASGI y obtiene health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_micelia_client_health_against_asgi_app(sdk_client_against_micelia):
    """
    MiceliaClient.health_check() contra la FastAPI app de Micelia (ASGI)
    devuelve un body con un `status` reconocible.
    """
    client, _app = sdk_client_against_micelia

    result = await client.health_check()
    assert isinstance(result, dict)
    # Distintos endpoints devuelven {status: "ok"|"healthy"|"degraded"|...}.
    assert "status" in result
    assert isinstance(result["status"], str)


# ---------------------------------------------------------------------------
# 4) source="micelia" emitido vía SDK persiste con ese source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sdk_publishes_event_with_micelia_source(sdk_client_against_micelia):
    """
    El SDK emite eventos con `source=self.config.service_name`. Configuramos
    el service_name a "micelia" y verificamos:
      - status 200/201 + body['status']=='created'
      - el event_store recibió `source='micelia'`.
    """
    client, app = sdk_client_against_micelia
    # Forzamos el service_name del SDK a "micelia" para este caso E2E.
    client.config.service_name = "micelia"

    result = await client.publish_event(
        category="system",
        action="test.sdk.micelia",
        payload={"k": "v"},
        event_type="sdk",
    )

    assert result["status"] == "created"
    assert "event_id" in result

    store = app.state.event_store
    store.append_event.assert_awaited()
    call_kwargs = store.append_event.await_args.kwargs
    assert call_kwargs["source"] == "micelia"
    assert call_kwargs["category"] == "system"
    assert call_kwargs["action"] == "test.sdk.micelia"


# ---------------------------------------------------------------------------
# 5) source="idm-core" legacy: round-trip exitoso desde el SDK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sdk_publishes_event_with_legacy_idm_core_source(
    sdk_client_against_micelia,
):
    """
    El SDK emite con `source='idm-core'` (legacy). El endpoint debe
    seguir respondiendo OK; la normalización + DeprecationWarning vive en
    `EventStore.append_event` y está cubierta por
    `tests/e2e/test_source_id.py`. Aquí sólo validamos que el SDK no
    rompe con el source legacy.
    """
    client, app = sdk_client_against_micelia
    client.config.service_name = "idm-core"

    result = await client.publish_event(
        category="system",
        action="test.sdk.legacy",
        payload={"legacy": True},
    )

    assert result["status"] == "created"
    store = app.state.event_store
    call_kwargs = store.append_event.await_args.kwargs
    # El mock no normaliza; pasa el valor literal recibido en el endpoint.
    assert call_kwargs["source"] == "idm-core"


# ---------------------------------------------------------------------------
# 6) MiceliaServiceClient (app-internal SDK): kwarg legacy
# ---------------------------------------------------------------------------


def test_micelia_service_client_accepts_micelia_url_kwarg():
    """`MiceliaServiceClient(micelia_url=...)` se construye sin warnings."""
    import warnings

    from app.sdk import MiceliaServiceClient

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = MiceliaServiceClient(
            service_name="biohack-app",
            port=8080,
            category="health",
            micelia_url="http://micelia:8888",
            api_key="k",
        )

    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecations == [], (
        "MiceliaServiceClient con `micelia_url=` no debería emitir "
        f"DeprecationWarning; got: {[str(w.message) for w in deprecations]}"
    )
    assert client.micelia_url == "http://micelia:8888"
    assert client.service_name == "biohack-app"


def test_micelia_service_client_accepts_legacy_idm_core_url_with_warning():
    """
    `MiceliaServiceClient(idm_core_url=...)` emite `DeprecationWarning` y
    sigue construyendo el cliente, asignando el valor a `micelia_url`.
    Esta es la garantía explícita de retro-compat de T1.3.
    """
    from app.sdk import MiceliaServiceClient

    with pytest.warns(DeprecationWarning, match=r"idm_core_url|deprec"):
        client = MiceliaServiceClient(
            service_name="biohack-app",
            port=8080,
            category="health",
            idm_core_url="http://idm-core:8888",
            api_key="k",
        )

    assert client.micelia_url == "http://idm-core:8888"


def test_micelia_service_client_idm_service_client_alias():
    """
    `IdmServiceClient` debe ser alias del mismo símbolo que
    `MiceliaServiceClient` (o subclase). Verifica retro-compat de imports.
    """
    from app.sdk import IdmServiceClient, MiceliaServiceClient

    assert IdmServiceClient is MiceliaServiceClient or issubclass(
        IdmServiceClient, MiceliaServiceClient
    )
