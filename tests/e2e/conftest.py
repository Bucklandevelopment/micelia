# conftest for the E2E test suite.
#
# Esta carpeta contiene tests end-to-end de la API de Micelia (antes vital-core)
# usando un ASGI client real contra la app FastAPI y `respx` / `pytest-httpx`
# para interceptar las llamadas HTTP salientes hacia servicios upstream
# (biohack-app, integraciones externas, etc.).
#
# T2.2: la fixture `biohack_mock` (function-scoped) y `biohack_mock_module`
# (module-scoped) montan un mock server in-process basado en respx con las
# respuestas canónicas del contrato Micelia <-> biohack-app definidas en T2.1.
#
# T3.1: añadimos fixtures `e2e_client` (cliente ASGI con `app.state.http_client`
# reemplazado por un httpx.AsyncClient real para que respx pueda interceptar)
# y `api_key` (alias de `auth_headers` del conftest raíz para alinear nombre
# con el brief T3.x).

from typing import AsyncGenerator
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Re-exporta las fixtures del mock biohack-app para que sean visibles en
# cualquier test de tests/e2e/** sin necesidad de import explícito.
from tests.e2e.mocks.biohack_server import (  # noqa: F401
    biohack_mock,
    biohack_mock_module,
)

# Aplica el marcador asyncio a todos los tests de esta carpeta.
pytestmark = pytest.mark.asyncio


@pytest.fixture()
def api_key(auth_headers: dict) -> dict:
    """Alias de ``auth_headers`` (conftest raíz) bajo el nombre del brief T3.x.

    El brief de T3.1 usa la variable ``api_key`` para los headers; mantenemos
    una fixture específica para que los tests E2E lean igual que el brief.
    """
    return auth_headers


@pytest.fixture()
async def e2e_client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """ASGI client preparado para interceptación respx.

    El conftest raíz (``tests/conftest.py``) instala un ``AsyncMock`` como
    ``test_app.state.http_client`` que devuelve siempre 500 — útil para los
    tests unitarios que no quieren tráfico saliente, pero incompatible con
    respx (los AsyncMock no pasan por el transport de httpx que respx
    patchea).

    Esta fixture:

    1. Sustituye ``test_app.state.http_client`` por un ``httpx.AsyncClient``
       real durante la vida del test. ``respx.mock(...)`` (montado por
       ``biohack_mock``) intercepta sus requests porque parchea
       ``httpx`` a nivel de módulo.
    2. Inyecta un ``AsyncMock`` como ``event_store`` para que los endpoints
       de ``/api/v1/events`` respondan 200 sin tocar BD real.
    3. Restaura el estado original al finalizar.
    """
    original_http_client = test_app.state.http_client
    original_event_store = test_app.state.event_store

    real_http_client = httpx.AsyncClient()
    mock_event_store = AsyncMock()
    mock_event_store.append_event = AsyncMock(return_value=uuid4())
    mock_event_store.query_events = AsyncMock(return_value=[])

    test_app.state.http_client = real_http_client
    test_app.state.event_store = mock_event_store

    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
        ) as ac:
            # Adjuntamos el mock store para que el test pueda hacer asserts
            # sobre el append_event recibido sin tener que volver a
            # localizarlo en app.state.
            ac.event_store = mock_event_store  # type: ignore[attr-defined]
            yield ac
    finally:
        await real_http_client.aclose()
        test_app.state.http_client = original_http_client
        test_app.state.event_store = original_event_store
