"""
E2E tests para el gateway de Micelia (T3.3).

Verifica que ``app/api/v1/gateway.py:proxy_health_service`` reenvía
correctamente las requests al servicio biohack-app (mockeado con respx vía
``biohack_mock``), preservando:

  1. Path y método HTTP (GET simple).
  2. Query params (GET con ``?user_id=...&metric=...``).
  3. Body JSON (POST a Bio-Savant chat).
  4. Headers del cliente (X-API-Key, X-Request-Id) hacia el upstream.
  5. Códigos de error upstream (modo ``"down"`` → 5xx propagado).

Mapping real del gateway
------------------------
El router en ``app/api/v1/gateway.py`` declara ``prefix="/gateway"`` y la
ruta ``/health/{path:path}`` proxea a biohack-app. El app de test monta el
router con ``prefix="/api/v1"``, así que la URL completa desde el cliente
es::

    /api/v1/gateway/health/<sub-path>

El path enviado al upstream es ``/<sub-path>`` (sin el prefijo de Micelia).
Por ejemplo: ``GET /api/v1/gateway/health/api/v1/health/live`` proxea a
``GET {settings.health_service_url}/api/v1/health/live``.

Notas
-----
- El conftest base (``tests/conftest.py``) inyecta un ``AsyncMock`` como
  ``app.state.http_client``. Para que respx pueda interceptar las llamadas
  del gateway necesitamos un ``httpx.AsyncClient`` real; la fixture local
  ``gateway_client`` se encarga de instalarlo y restaurarlo.
- ``biohack_mock._mock`` es el ``respx.MockRouter`` subyacente; sus
  ``.calls`` permiten inspeccionar las requests recibidas.
"""

from __future__ import annotations

from typing import AsyncGenerator

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from tests.e2e.mocks.contracts import (
    BiomarkerSeries,
    BioSavantChatResponse,
    HealthStatus,
)

pytestmark = pytest.mark.asyncio


# Prefijo público del gateway dentro de la app montada en tests.
# El router declara prefix="/gateway", el app lo monta bajo "/api/v1".
GATEWAY_HEALTH_PREFIX = "/api/v1/gateway/health"


@pytest.fixture()
async def gateway_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """
    Cliente ASGI con un ``httpx.AsyncClient`` real instalado en
    ``app.state.http_client`` para que respx pueda interceptar las
    llamadas upstream del gateway.

    Restaura el cliente mockeado original al finalizar.
    """
    original_http_client = test_app.state.http_client
    real_upstream_client = httpx.AsyncClient()
    test_app.state.http_client = real_upstream_client

    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
        ) as ac:
            yield ac
    finally:
        await real_upstream_client.aclose()
        test_app.state.http_client = original_http_client


# =============================================================================
# 1. GET simple
# =============================================================================


async def test_gateway_get_health_live_proxies_to_biohack(
    biohack_mock, gateway_client, auth_headers
):
    """GET /api/v1/gateway/health/api/v1/health/live → biohack devuelve
    HealthStatus(status='alive'). El gateway debe devolver el body intacto."""
    biohack_mock.set_mode("healthy")

    resp = await gateway_client.get(
        f"{GATEWAY_HEALTH_PREFIX}/api/v1/health/live",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Validar contrato: debe parsear como HealthStatus con status=alive.
    parsed = HealthStatus.model_validate(body)
    assert parsed.status == "alive"
    assert parsed.service == "biohack-app"

    # El mock recibió exactamente una llamada.
    assert len(biohack_mock._mock.calls) == 1
    upstream_request = biohack_mock._mock.calls.last.request
    assert upstream_request.method == "GET"
    assert upstream_request.url.path == "/api/v1/health/live"


# =============================================================================
# 2. GET con query params
# =============================================================================


async def test_gateway_get_biomarkers_series_preserves_query_params(
    biohack_mock, gateway_client, auth_headers
):
    """GET /…/biomarkers/series?user_id=u_42&metric=hrv proxea la query
    al mock, que responde con una BiomarkerSeries válida."""
    biohack_mock.set_mode("healthy")

    resp = await gateway_client.get(
        f"{GATEWAY_HEALTH_PREFIX}/api/v1/biomarkers/series",
        params={"user_id": "u_42", "metric": "hrv"},
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Body intacto: parsea como BiomarkerSeries para u_42/hrv.
    parsed = BiomarkerSeries.model_validate(body)
    assert parsed.user_id == "u_42"
    assert parsed.metric == "hrv"
    assert parsed.unit == "ms"
    assert len(parsed.points) == 30  # mock genera 30 puntos diarios.

    # El upstream recibió la query con los dos params.
    assert len(biohack_mock._mock.calls) == 1
    upstream_request = biohack_mock._mock.calls.last.request
    assert upstream_request.url.path == "/api/v1/biomarkers/series"
    upstream_query = dict(upstream_request.url.params)
    assert upstream_query == {"user_id": "u_42", "metric": "hrv"}


# =============================================================================
# 3. POST con JSON body
# =============================================================================


async def test_gateway_post_bio_savant_forwards_json_body(
    biohack_mock, gateway_client, auth_headers
):
    """POST /…/bio-savant/chat con body JSON → biohack recibe el body y
    devuelve BioSavantChatResponse. El gateway devuelve la respuesta
    tal cual."""
    biohack_mock.set_mode("healthy")

    request_body = {"message": "hola", "health_context": {}}
    resp = await gateway_client.post(
        f"{GATEWAY_HEALTH_PREFIX}/api/v1/bio-savant/chat",
        json=request_body,
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Valida contrato de respuesta.
    parsed = BioSavantChatResponse.model_validate(body)
    assert parsed.answer  # non-empty
    assert len(parsed.sources) >= 1

    # El upstream recibió el body JSON intacto.
    assert len(biohack_mock._mock.calls) == 1
    upstream_request = biohack_mock._mock.calls.last.request
    assert upstream_request.method == "POST"
    assert upstream_request.url.path == "/api/v1/bio-savant/chat"
    import json

    received_body = json.loads(upstream_request.content)
    assert received_body == request_body


# =============================================================================
# 4. Propagación de headers
# =============================================================================


async def test_gateway_forwards_client_headers_upstream(
    biohack_mock, gateway_client, auth_headers
):
    """Cliente envía X-API-Key + X-Request-Id; el upstream debe recibirlos
    tal cual (modulo casing canónico de httpx)."""
    biohack_mock.set_mode("healthy")

    headers = {
        **auth_headers,
        "X-Request-Id": "abc123",
    }
    resp = await gateway_client.get(
        f"{GATEWAY_HEALTH_PREFIX}/api/v1/health/live",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    assert len(biohack_mock._mock.calls) == 1
    upstream_request = biohack_mock._mock.calls.last.request

    # httpx normaliza nombres de header a lowercase en el dict interno.
    upstream_headers = {
        k.lower(): v for k, v in upstream_request.headers.items()
    }
    # X-API-Key: viene de auth_headers; comparamos por valor, no por key
    # exacta (el manager genera una key opaca al inicio de la suite).
    assert "x-api-key" in upstream_headers
    assert upstream_headers["x-api-key"] == auth_headers["X-API-Key"]
    assert upstream_headers.get("x-request-id") == "abc123"


# =============================================================================
# 5. Error upstream propagado (modo "down")
# =============================================================================


async def test_gateway_propagates_upstream_error_when_biohack_down(
    biohack_mock, gateway_client, auth_headers
):
    """Con biohack en modo 'down' (503 en todos los endpoints), el gateway
    debe devolver un código 5xx con mensaje claro al cliente."""
    biohack_mock.set_mode("down")

    resp = await gateway_client.get(
        f"{GATEWAY_HEALTH_PREFIX}/api/v1/health/live",
        headers=auth_headers,
    )

    # El gateway propaga la respuesta upstream (503) tal cual. Aceptamos
    # cualquier 5xx para no acoplar el test a la implementación exacta
    # (proxy_request reusa el status_code del upstream, así que será 503).
    assert 500 <= resp.status_code < 600, resp.text
    body = resp.json()
    # El payload debe contener una indicación clara del fallo.
    detail = body.get("detail", "")
    assert isinstance(detail, str)
    assert detail  # mensaje no vacío

    # El upstream sí fue invocado (el mock contó la llamada antes del 503).
    assert len(biohack_mock._mock.calls) == 1
