"""
C86 — Guard EJECUTABLE de la cadena de registro dominio→store que C83 verificó A MANO.

C83 (2026-07-16) arrancó por primera vez el gateway de verdad y registró un dominio
real contra él, descubriendo la semántica REAL del "registro": el `register()` del SDK
**no crea una entrada en el registry** (ese es PULL: Micelia sondea `/health`). Lo que
hace es `POST /api/v1/events` con un evento `service.registered`, que aterriza en el
**Event Store**. Y el sistema tiene DOS gates, observados en vivo como la secuencia
`401 → 503 → OK`:

  1. auth — sin API key válida, el POST es **401** (verify_auth, dependency del router).
  2. store — con la key pero sin Event Store (postgres caído), el POST es **503**
     ("Event store not available") y el dominio degrada en SILENCIO: nunca se registra.
  3. con ambos, **200/201** y el evento queda consultable en el store.

Hasta C86 esa cadena solo estaba verificada A MANO (C83 la ejerció una vez y la anotó).
Este módulo la pinea de forma ejecutable, con el cliente SDK REAL (`IdmServiceClient`,
no un mock) hablando con la app REAL vía ASGITransport (in-process, sin bindear puerto):

  * los dos primeros gates (401, 503) NO necesitan postgres — se ejercen contra la app
    sintética con `event_store=None`, así que corren siempre.
  * el tramo final (OK + evento en el store) exige un Event Store real → `require_postgres`
    lo salta si no hay postgres, y arranca el LIFESPAN REAL del gateway (`app.main:app`),
    que es quien inicializa el store — con `no_domain_probes` para no reintroducir la
    no-hermeticidad de sondeo que C85 cazó.

Reusa `TEST_API_KEY` (registrado en el `api_key_manager` singleton por conftest) como la
"SYSTEM_API_KEY propia" del test — sin leer el `.env` real.
"""

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

import app.sdk.client as sdk_client
from app.api.v1 import events
from tests.conftest import TEST_API_KEY

pytestmark = pytest.mark.asyncio

# El source-id canónico del dominio de seguridad; es uno de los 6 oficiales del
# ecosistema (ver EventCreate en app/api/v1/events.py). No renombrar.
_SOURCE = "cybertools"


def _events_only_app(event_store) -> FastAPI:
    """
    App mínima con SOLO el router de eventos real (incluye `verify_auth` como dependency).

    Sirve para ejercer los gates de auth/store SIN arrancar el lifespan completo ni
    exigir postgres: el camino `POST /api/v1/events → verify_auth → create_event →
    app.state.event_store` es idéntico al del gateway real (mismo router, misma
    dependency), sólo que `event_store` se inyecta explícitamente (None para el gate 503).
    """
    app = FastAPI()
    app.state.event_store = event_store
    app.include_router(events.router, prefix="/api/v1")
    return app


def _sdk_client(app: FastAPI, *, api_key: str):
    """IdmServiceClient REAL cuyo http-client habla con `app` in-process (ASGITransport)."""
    from app.sdk.client import IdmServiceClient

    client = IdmServiceClient(
        service_name=_SOURCE,
        port=8000,
        category="security",
        micelia_url="http://test",
        api_key=api_key,
        version="1.0.0",
        capabilities=["nmap-scan", "vuln-scan"],
        heartbeat_interval=0,  # sin loop de fondo: el test controla el ciclo
    )
    headers = {"X-API-Key": api_key} if api_key else {}
    client._http_client = httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers,
    )
    return client


# =============================================================================
# Gate 1 — auth (sin postgres)
# =============================================================================


async def test_register_without_api_key_is_rejected_401():
    """
    Sin API key, el POST de registro es 401 (gate de auth). Se ejerce el endpoint real
    directamente para VER el 401 — el SDK lo traga y devuelve False (ver el test
    siguiente), así que aquí lo miramos crudo. C83 lo observó en vivo (api_key vacía →
    "Registration returned 401: Authentication required...").
    """
    app = _events_only_app(event_store=object())  # store presente: el 401 salta antes
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as raw:
        resp = await raw.post(
            "/api/v1/events",
            json={
                "category": "system",
                "source": _SOURCE,
                "action": "create",
                "event_type": "service.registered",
                "payload": {"service_name": _SOURCE},
            },
        )
    assert resp.status_code == 401, resp.text
    assert "Authentication" in resp.text or "API key" in resp.text


async def test_sdk_register_swallows_401_and_returns_false():
    """
    El SDK REAL, con key vacía, degrada en silencio: `register()` devuelve False (no
    lanza). Es la cara del gate de auth que ve el dominio — el fallo SILENCIOSO que C83
    documentó. Pinea el contrato del SDK: nunca propaga, siempre reporta bool.
    """
    app = _events_only_app(event_store=object())
    client = _sdk_client(app, api_key="")
    try:
        assert await client.register() is False
    finally:
        await client._http_client.aclose()


# =============================================================================
# Gate 2 — store (sin postgres)
# =============================================================================


async def test_register_with_key_but_no_store_is_503():
    """
    Con API key VÁLIDA pero sin Event Store (`app.state.event_store = None`), el POST es
    503 "Event store not available". Es el 2º gate de C83: un dominio nunca se registra
    si el store está caído — y lo hace en silencio. Se ejerce crudo para ver el 503.
    """
    app = _events_only_app(event_store=None)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": TEST_API_KEY},
    ) as raw:
        resp = await raw.post(
            "/api/v1/events",
            json={
                "category": "system",
                "source": _SOURCE,
                "action": "create",
                "event_type": "service.registered",
                "payload": {"service_name": _SOURCE},
            },
        )
    assert resp.status_code == 503, resp.text
    assert "Event store" in resp.text


# =============================================================================
# Cadena completa — OK + evento en el store (exige postgres)
# =============================================================================


async def test_sdk_register_lands_service_registered_event_in_real_store(
    require_postgres, no_domain_probes
):
    """
    LA cadena que C83 ejerció a mano, ahora ejecutable de punta a punta:

    arranca el LIFESPAN REAL del gateway (`app.main:app`, que inicializa el Event Store
    real que `require_postgres` garantizó) → el cliente SDK REAL con `TEST_API_KEY` llama
    `register()` → el evento `service.registered` con `source='cybertools'` aterriza en
    el store y es consultable. `no_domain_probes` mantiene los sondeos del registry
    herméticos (no bindeamos puerto: el SDK habla con la app por ASGITransport).
    """
    from app.main import app

    async with app.router.lifespan_context(app):
        store = app.state.event_store
        assert store is not None, (
            "require_postgres pasó pero el lifespan no inicializó el Event Store — "
            "regresión en el wiring de app.main:lifespan"
        )

        # Cuántos service.registered de este source había antes (aislamiento entre
        # corridas: el store es append-only y persiste; contamos el delta, no el total).
        before = await store.query_events(
            source=_SOURCE, event_type="service.registered", limit=1000
        )

        client = _sdk_client(app, api_key=TEST_API_KEY)
        try:
            registered = await client.register()
        finally:
            await client._http_client.aclose()

        assert registered is True, "register() devolvió False con key válida + store vivo"

        after = await store.query_events(
            source=_SOURCE, event_type="service.registered", limit=1000
        )
        assert len(after) == len(before) + 1, (
            f"register() no dejó exactamente 1 evento nuevo en el store "
            f"(antes={len(before)}, después={len(after)})"
        )

        newest = after[0]  # query_events ordena por timestamp desc
        assert newest["source"] == _SOURCE
        assert newest["event_type"] == "service.registered"
        # El payload que el SDK arma en register() debe viajar íntegro hasta el store.
        payload = newest["payload"]
        assert payload["service_name"] == _SOURCE
        assert payload["status"] == "starting"
        assert "vuln-scan" in payload["capabilities"]


# =============================================================================
# HEARTBEAT — la 2ª mitad del contrato de C83 (C88)
# =============================================================================
#
# C83 observó en el store, en vivo: `{'service.registered': 1, 'service.heartbeat': 2,
# 'system.initialized': 1}` — el `register()` (pineado arriba) Y el latido de 30s
# funcionando. C86 pineó solo el register; C88 cierra el latido. El heartbeat es el
# MISMO camino que register (POST /api/v1/events → verify_auth → store) pero con
# `event_type='service.heartbeat'`, `action='update'`, `tags=['heartbeat']` y un payload
# que es el `health_response()` del SDK (status/version/service/category/port/
# capabilities/uptime_seconds/dependencies). Y encima hay un LOOP que lo repite cada
# `heartbeat_interval` segundos — eso se pinea aparte, determinista, sin reloj de pared.


async def test_sdk_heartbeat_without_store_is_503_returns_false():
    """
    Sin Event Store, un latido degrada en SILENCIO igual que el register: el POST es 503
    y `heartbeat()` devuelve False sin lanzar. Es la misma semántica de fallo silencioso
    que C83 documentó — un dominio "vivo" cuyos latidos se pierden si el store cae. Sin
    postgres (el gate 503 salta antes de tocar el store).
    """
    app = _events_only_app(event_store=None)
    client = _sdk_client(app, api_key=TEST_API_KEY)
    try:
        assert await client.heartbeat() is False
    finally:
        await client._http_client.aclose()


async def test_heartbeat_loop_sends_periodic_heartbeats(monkeypatch):
    """
    El loop de fondo (`_heartbeat_loop`) llama a `heartbeat()` UNA VEZ por intervalo, en
    bucle, hasta que se cancela. Se pinea SIN reloj de pared ni postgres: se parchea
    `asyncio.sleep` (en el módulo del SDK) por un stub que cuenta y corta a la 4ª llamada
    con CancelledError, y se cuenta cuántas veces se invocó `heartbeat`. Mismo patrón que
    `test_continuous_monitoring_runs_one_cycle_then_cancels` del registry.

    Estructura del loop: `while True: await sleep(interval); await heartbeat()`. Con el
    corte en la 4ª sleep → exactamente 3 latidos (sleeps 1,2,3 → heartbeat; sleep 4 →
    cancel antes del 4º). Que sea `heartbeat_interval` quien gobierne la cadencia lo fija
    el hecho de que el stub sustituye ESA espera.
    """
    client = sdk_client.IdmServiceClient(
        service_name=_SOURCE,
        port=8000,
        category="security",
        api_key=TEST_API_KEY,
        heartbeat_interval=30,  # el valor real; el stub de sleep lo intercepta
    )

    beats = {"n": 0}
    sleeps = {"n": 0}

    async def fake_heartbeat() -> bool:
        beats["n"] += 1
        return True

    async def fake_sleep(_seconds):
        sleeps["n"] += 1
        if sleeps["n"] >= 4:
            raise asyncio.CancelledError

    monkeypatch.setattr(client, "heartbeat", fake_heartbeat)
    monkeypatch.setattr(sdk_client.asyncio, "sleep", fake_sleep)

    await client._heartbeat_loop()

    assert beats["n"] == 3, f"el loop no latió 3 veces antes del cancel (n={beats['n']})"


async def test_sdk_heartbeat_lands_service_heartbeat_event_in_real_store(
    require_postgres, no_domain_probes
):
    """
    La 2ª mitad de C83, ejecutable de punta a punta: gateway REAL (lifespan) + SDK REAL →
    `heartbeat()` deja un `service.heartbeat` con `source='cybertools'` en el store, con
    el payload de `health_response()` íntegro (service, status, version, port). Espejo del
    test de register de C86; juntos pinean las DOS entradas que C83 vio en el store.
    """
    from app.main import app

    async with app.router.lifespan_context(app):
        store = app.state.event_store
        assert store is not None, (
            "require_postgres pasó pero el lifespan no inicializó el Event Store"
        )

        before = await store.query_events(
            source=_SOURCE, event_type="service.heartbeat", limit=1000
        )

        client = _sdk_client(app, api_key=TEST_API_KEY)
        try:
            beat_ok = await client.heartbeat()
        finally:
            await client._http_client.aclose()

        assert beat_ok is True, "heartbeat() devolvió False con key válida + store vivo"

        after = await store.query_events(
            source=_SOURCE, event_type="service.heartbeat", limit=1000
        )
        assert len(after) == len(before) + 1, (
            f"heartbeat() no dejó exactamente 1 evento nuevo "
            f"(antes={len(before)}, después={len(after)})"
        )

        newest = after[0]
        assert newest["source"] == _SOURCE
        assert newest["event_type"] == "service.heartbeat"
        # El payload es el health_response() del SDK (models.HealthResponse.to_dict()).
        payload = newest["payload"]
        assert payload["service"] == _SOURCE
        assert payload["status"] == "healthy"  # _healthy=True por defecto
        assert payload["port"] == 8000
        assert payload["version"] == "1.0.0"
