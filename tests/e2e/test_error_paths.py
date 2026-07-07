"""
E2E tests para paths de error y resiliencia de Micelia (T3.2).

Verifica que la API responde con códigos de error correctos y mensajes
útiles frente a:

  1. Llamadas sin autenticación  (401)
  2. Permisos insuficientes      (403, si el modelo de permisos lo cubre)
  3. Upstream biohack-app caído  (5xx no-500-fatal vía gateway)
  4. Upstream biohack-app lento  (504 si Micelia configura timeout)
  5. Body inválido               (422)
  6. Rate limit excedido         (429, si hay rate-limiting aplicado)

Casos no factibles (por ausencia de feature en producción) se SALTAN con
``pytest.skip("razón")`` en vez de pasar falsamente — mantenemos honestos
los tests y dejamos rastro de qué falta por implementar.

Notas de diseño
===============
- ``client`` y ``auth_headers`` se reutilizan desde ``tests/conftest.py``.
  ``api_key`` es alias de ``auth_headers`` provisto por
  ``tests/e2e/conftest.py`` (T3.1).
- ``e2e_client`` (de ``tests/e2e/conftest.py``) reemplaza
  ``app.state.http_client`` por un ``httpx.AsyncClient`` real, requisito
  para que respx pueda interceptar las llamadas salientes del gateway
  hacia biohack-app. Lo reutilizamos para los tests que pasan por el
  proxy.
- ``biohack_mock`` (de ``tests/e2e/mocks/biohack_server.py``) controla la
  simulación de biohack-app (modos healthy/degraded/down/slow).
"""

from __future__ import annotations

from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.security import api_key_manager

pytestmark = pytest.mark.asyncio


# =============================================================================
# Fixtures locales
# =============================================================================


# API key con permisos restringidos: sólo "read", sin "all" ni "write".
# Generada a nivel de módulo para que persista durante toda la suite.
READONLY_API_KEY = api_key_manager.generate_key(
    name="test-readonly",
    permissions={"read"},
    rate_limit=10000,
)


# API key con rate_limit bajo (10/min) para el caso de 429.
RATE_LIMITED_API_KEY = api_key_manager.generate_key(
    name="test-rate-limited",
    permissions={"all"},
    rate_limit=10,
)


@pytest.fixture()
def readonly_headers() -> dict:
    """Headers con una API key válida pero limitada a permiso 'read'."""
    return {"X-API-Key": READONLY_API_KEY}


@pytest.fixture()
def rate_limited_headers() -> dict:
    """Headers con una API key válida pero con rate_limit=10/min."""
    return {"X-API-Key": RATE_LIMITED_API_KEY}


@pytest.fixture()
async def short_timeout_gateway_client(
    test_app: FastAPI,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Variante de ``e2e_client`` con timeout cortísimo en el httpx real
    (0.4 s). Necesaria para el test de upstream slow sin gastar el
    presupuesto de 3 s del suite. Restaura el estado original al
    finalizar.
    """
    original_http = test_app.state.http_client
    real_http = httpx.AsyncClient(timeout=0.4)
    test_app.state.http_client = real_http
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
        ) as ac:
            yield ac
    finally:
        await real_http.aclose()
        test_app.state.http_client = original_http


# =============================================================================
# 1) 401 — Sin API key
# =============================================================================


async def test_events_post_without_api_key_returns_401(client):
    """POST /api/v1/events sin header X-API-Key → 401."""
    body = {
        "category": "health",
        "source": "biohack",
        "event_type": "test.no_auth",
        "action": "create",
    }
    resp = await client.post("/api/v1/events", json=body)
    assert resp.status_code == 401, resp.text
    detail = resp.json()
    assert "detail" in detail
    # El handler verify_auth devuelve un mensaje pidiendo X-API-Key o Bearer.
    assert (
        "Authentication" in detail["detail"]
        or "API key" in detail["detail"]
        or "Bearer" in detail["detail"]
    )


async def test_events_list_without_api_key_returns_401(client):
    """GET /api/v1/events sin header X-API-Key → 401 (caso del brief)."""
    resp = await client.get("/api/v1/events")
    assert resp.status_code == 401, resp.text


async def test_events_with_invalid_api_key_returns_401(client):
    """X-API-Key con valor inválido → 401 con detail explicativo."""
    resp = await client.get(
        "/api/v1/events",
        headers={"X-API-Key": "not-a-real-key-deadbeef"},
    )
    assert resp.status_code == 401, resp.text
    body = resp.json()
    assert "detail" in body
    assert "Invalid" in body["detail"] or "API key" in body["detail"]


# =============================================================================
# 2) 403 — Permisos insuficientes
# =============================================================================


async def test_permissions_insufficient_returns_403(client, readonly_headers):
    """
    Permisos insuficientes: el modelo de permisos en ``app/core/security.py``
    distingue ``"all"``, ``"read"`` y ``"write"``, pero el router de events
    (y los otros routers del flujo Micelia ↔ biohack-app) sólo usan
    ``verify_auth`` para validar *que existe* una API key válida, sin
    chequear el set de permisos. Los checks de permiso
    (``require_write_permission``, ``has_permission``) sólo se aplican a
    operaciones OSASCRIPT, no a los endpoints E2E bajo tests.

    Como consecuencia, una API key con ``permissions={"read"}`` puede
    crear eventos igual que una con ``permissions={"all"}``. No hay un
    403 observable en el flujo Micelia ↔ biohack-app sin tocar ``app/``.
    """
    pytest.skip(
        "No hay endpoint Micelia que retorne 403 por permisos en el flujo "
        "actual: verify_auth sólo valida existencia de la key, no su set "
        "de permisos. Los chequeos has_permission viven en el módulo "
        "OSASCRIPT (no E2E) y aplicarlos al gateway/events requeriría "
        "modificar app/api/v1/events.py o app/api/v1/gateway.py."
    )


# =============================================================================
# 3) 503 — Upstream biohack-app down (vía gateway proxy)
# =============================================================================


async def test_gateway_health_with_biohack_down_returns_5xx(
    biohack_mock, e2e_client, api_key
):
    """
    Con ``biohack_mock.set_mode("down")``, una request al gateway proxy
    hacia biohack-app debe degradar grácilmente: cualquier 5xx que NO sea
    500 fatal es aceptable. El gateway puede devolver:
      - 503: biohack respondió 503 (status_code propagado por el proxy)
      - 502: si Micelia mapeó el error upstream a Bad Gateway
      - 504: si la connect tardó demasiado
    """
    biohack_mock.set_mode("down")

    resp = await e2e_client.get(
        "/api/v1/gateway/health/detailed",
        headers=api_key,
    )

    # NO 500: 500 indicaría que Micelia se cayó por su cuenta, no que
    # tradujo el fallo del upstream a un error razonable.
    assert resp.status_code != 500, (
        f"Micelia falló con 500 (no es degradación grácil): {resp.text}"
    )
    # Cualquier 5xx 'razonable' (502/503/504) es aceptable.
    assert resp.status_code in (502, 503, 504), (
        f"Status inesperado en biohack down: {resp.status_code} / {resp.text}"
    )

    # Debe haber un mensaje claro, no un stacktrace.
    try:
        body = resp.json()
    except ValueError:
        pytest.fail(f"Respuesta no-JSON en biohack down: {resp.text}")
    assert "detail" in body or "error" in body, resp.text


# =============================================================================
# 4) 504/timeout — Upstream slow
# =============================================================================


async def test_gateway_health_with_biohack_slow_returns_504(
    biohack_mock, short_timeout_gateway_client, api_key
):
    """
    Con ``biohack_mock.set_mode("slow")``, biohack-app duerme antes de
    responder. Con ``settings.service_timeout`` por defecto (10 s) y el
    delay default del mock (2 s) el timeout NO dispara — para no gastar
    todo el presupuesto de 3 s del suite, usamos un httpx.AsyncClient
    con timeout 0.4 s y reducimos el slow_delay del mock a 0.8 s, así
    el test corre en <1 s y produce un 504 verificable.
    """
    # Reconfigurar el mock para un slow_delay corto pero > timeout (0.4 s).
    biohack_mock.slow_delay_seconds = 0.8
    biohack_mock.set_mode("slow")

    resp = await short_timeout_gateway_client.get(
        "/api/v1/gateway/health/detailed",
        headers=api_key,
    )

    # Aceptamos 504 (gateway timeout, lo que el handler emite explícitamente
    # ante httpx.TimeoutException) o 502 si se envuelve genéricamente.
    # NO debe ser 500 ni propagar excepción.
    assert resp.status_code != 500, resp.text
    assert resp.status_code in (502, 503, 504), (
        f"Status inesperado en biohack slow: {resp.status_code} / {resp.text}"
    )

    body = resp.json()
    assert "detail" in body or "error" in body
    if resp.status_code == 504:
        # El mensaje debería mencionar timeout para ser útil al operador.
        detail = str(body.get("detail", "")) + str(body.get("error", ""))
        assert "timeout" in detail.lower(), (
            f"504 sin mención de timeout en detail: {body}"
        )


# =============================================================================
# 5) 422 — Validación de body
# =============================================================================


async def test_create_event_with_missing_fields_returns_422(
    client, auth_headers
):
    """
    POST /api/v1/events con body {"category": "health"} (faltan source,
    event_type, action). FastAPI/Pydantic debe responder 422 con detail
    que enumere los campos faltantes.
    """
    resp = await client.post(
        "/api/v1/events",
        json={"category": "health"},
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert "detail" in body
    # FastAPI devuelve una lista de errores; cada item tiene 'loc' y 'msg'.
    assert isinstance(body["detail"], list)
    missing_fields: set[str] = set()
    for item in body["detail"]:
        # Sólo nos quedamos con los errores de "missing field".
        type_ = item.get("type", "")
        msg = item.get("msg", "").lower()
        if (
            type_ in ("missing", "value_error.missing")
            or "missing" in msg
            or "required" in msg
            or "field required" in msg
        ):
            # ``loc`` es algo como ["body", "source"]; cogemos el último.
            loc = item.get("loc") or []
            if loc:
                missing_fields.add(str(loc[-1]))

    # Al menos los tres campos obligatorios deben aparecer.
    for required in ("source", "event_type", "action"):
        assert required in missing_fields, (
            f"Campo requerido '{required}' no reportado en 422: {body}"
        )


async def test_create_event_with_invalid_json_returns_422(
    client, auth_headers
):
    """JSON malformado (no parseable) → 422 sin caer con 500."""
    resp = await client.post(
        "/api/v1/events",
        content=b"{not valid json",
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert resp.status_code == 422, resp.text


# =============================================================================
# 6) 429 — Rate limit
# =============================================================================


async def test_events_rate_limit_returns_429(client, rate_limited_headers):
    """
    Rate limiting: el módulo ``app.core.security`` implementa un
    ``RateLimiter`` y el dependency ``check_rate_limit``, PERO sólo se
    aplica al subset OSASCRIPT (``osascript_security``) — NO al router
    de events ni al gateway. Por tanto enviar 11 requests rápidas con
    una key de ``rate_limit=10`` no dispara 429 en estos endpoints.

    Para habilitar este test habría que agregar ``check_rate_limit``
    como dependency al router de events / gateway en ``app/``, lo que
    está fuera del scope T3.2 (no tocamos código de producción).
    """
    pytest.skip(
        "Rate limiting (429) no está aplicado a /api/v1/events ni al "
        "gateway en la versión actual de Micelia: check_rate_limit sólo "
        "decora endpoints OSASCRIPT. Activar este test requiere añadir "
        "el dependency en app/api/v1/events.py o un middleware global "
        "de rate-limit; cambio fuera del scope T3.2."
    )
