"""
C92 — E2E cross-mecanismo: UN gateway ve al MISMO dominio por sus DOS canales a la vez.

C83 descubrió que Micelia tiene DOS mecanismos INDEPENDIENTES para saber de un dominio:
  - PUSH: el dominio hace `POST /api/v1/events` (register + heartbeat) → Event Store.
  - PULL: el registry SONDEA el `/health` del dominio → marca el slot healthy.
Y observó AMBOS a la vez sobre cybertools: el store con `{service.registered:1,
service.heartbeat:2}` Y el registry-pull virando `security` a `healthy=True`.

C86/C88/C90 pinearon cada mecanismo POR SEPARADO (register, heartbeat, pull). Este módulo
cierra lo que faltaba: que **coexisten sobre el mismo dominio en el mismo gateway**, y —lo
más importante de la tesis de C83— que son **INDEPENDIENTES**: que el registry marque un
dominio healthy (PULL) NO significa que ese dominio esté registrado en el store (PUSH), y
viceversa. Verificarlos por separado no es pedantería: miden cosas distintas.

Diseño (fiel + hermético): se arranca el LIFESPAN REAL del gateway, que trae SUS DOS
subsistemas reales — `app.state.event_store` (destino del PUSH) y `app.state.service_registry`
(motor del PULL). El PULL se dirige a un servidor `/health` real en un **puerto efímero que
el test posee** (no `localhost:<dominio>` — el eje que C89 cerró). El PUSH lo hace el cliente
SDK REAL por ASGITransport. El dominio es el mismo por ambos lados: `source='cybertools'`
(PUSH) sirviendo el slot `security` (PULL), igual que C83.

Exige postgres (Event Store) → `require_postgres` hace skip si no hay. `no_domain_probes`
mantiene herméticos los sondeos que el lifespan hace al arrancar (los OTROS slots).
"""

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from tests.conftest import TEST_API_KEY

pytestmark = pytest.mark.asyncio

_SOURCE = "cybertools"  # el source de los eventos PUSH (uno de los 6 canónicos)
_SLOT = "security"      # el slot del registry que cybertools sirve (PULL). Igual que C83.


@contextmanager
def _fake_domain_health(status_code: int, body: dict):
    """Servidor `/health` real en 127.0.0.1:<efímero que el test posee>. Cede su base_url."""
    payload = json.dumps(body).encode()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (nombre impuesto por la base)
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args, **kwargs):  # silenciar logging a stderr
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _sdk_client(app: FastAPI):
    """IdmServiceClient REAL (source=cybertools) hablando con `app` in-process."""
    from app.sdk.client import IdmServiceClient

    client = IdmServiceClient(
        service_name=_SOURCE,
        port=8000,
        category="security",
        micelia_url="http://test",
        api_key=TEST_API_KEY,
        version="1.0.0",
        capabilities=["nmap-scan", "vuln-scan"],
        heartbeat_interval=0,
    )
    client._http_client = httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": TEST_API_KEY},
    )
    return client


async def test_same_domain_alive_via_push_and_pull_and_they_are_independent(
    require_postgres, no_domain_probes
):
    """
    Un gateway real ve a cybertools por SUS DOS canales, y se demuestra que son
    independientes:

      1. PULL SOLO — el registry sondea el `/health` real del dominio → slot `security`
         healthy + version. En este punto el store NO tiene eventos nuevos: **el pull no
         escribe** (registry-healthy ⇏ registrado en el store).
      2. PUSH — el SDK real hace register()+heartbeat() contra el MISMO gateway → aparecen
         `service.registered` + `service.heartbeat` con source=cybertools en el store.
      3. COEXISTENCIA — al final, el gateway ve al dominio vivo por AMBOS: registry healthy
         (pull) Y store con register+heartbeat (push). Es lo que C83 vio a mano, ahora e2e.
    """
    from app.main import app

    async with app.router.lifespan_context(app):
        store = app.state.event_store
        registry = app.state.service_registry
        assert store is not None, "require_postgres pasó pero el lifespan no trajo store"
        assert _SLOT in registry.services, f"el registry no tiene el slot '{_SLOT}'"

        # Baseline del store (append-only; contamos deltas, no totales absolutos).
        async def _count(event_type: str) -> int:
            return len(
                await store.query_events(
                    source=_SOURCE, event_type=event_type, limit=5000
                )
            )

        base_reg = await _count("service.registered")
        base_hb = await _count("service.heartbeat")

        # --- (1) PULL SOLO: el registry sondea el /health real del dominio ---
        with _fake_domain_health(
            200, {"status": "healthy", "version": "1.0.0", "service": _SOURCE}
        ) as health_url:
            registry.services[_SLOT].url = health_url  # el slot apunta al dominio vivo
            await registry._check_health(_SLOT, "/health")

        assert registry.services[_SLOT].healthy is True
        assert registry.services[_SLOT].version == "1.0.0"

        # Independencia: el PULL no escribió NADA en el store. Un dominio healthy en el
        # registry puede no haberse registrado nunca (dos mecanismos distintos, C83).
        assert await _count("service.registered") == base_reg, (
            "el registry-pull dejó un service.registered en el store — los mecanismos "
            "PULL y PUSH dejarían de ser independientes (el pull debe ser read-only)"
        )
        assert await _count("service.heartbeat") == base_hb

        # --- (2) PUSH: el mismo dominio se registra y late contra el mismo gateway ---
        client = _sdk_client(app)
        try:
            assert await client.register() is True
            assert await client.heartbeat() is True
        finally:
            await client._http_client.aclose()

        assert await _count("service.registered") == base_reg + 1, (
            "register() no dejó exactamente 1 service.registered nuevo"
        )
        assert await _count("service.heartbeat") == base_hb + 1

        # --- (3) COEXISTENCIA: el gateway ve al dominio vivo por AMBOS canales ---
        # (el pull no se re-evalúa aquí; el slot sigue healthy de (1), y el store ya tiene
        # el push de (2) — las dos vistas del mismo dominio, simultáneas y de acuerdo.)
        assert registry.services[_SLOT].healthy is True
        newest_reg = (
            await store.query_events(
                source=_SOURCE, event_type="service.registered", limit=1
            )
        )[0]
        assert newest_reg["source"] == _SOURCE


async def test_push_without_pull_leaves_registry_slot_untouched(
    require_postgres, no_domain_probes
):
    """
    La otra cara de la independencia: un dominio que solo hace PUSH (register) —sin que el
    registry lo sondee— aterriza en el store PERO el slot del registry NO se vuelve healthy
    por ello. `register()` es un evento, no una alta en el registry (el registry es PULL).
    C83 lo dijo con todas las letras: "los dominios no pueden darse de alta; Micelia los
    descubre". Aquí se pinea ejecutable.
    """
    from app.main import app

    async with app.router.lifespan_context(app):
        store = app.state.event_store
        registry = app.state.service_registry
        assert store is not None

        # El slot arranca no-healthy (no_domain_probes lo apunta a un puerto cerrado).
        assert registry.services[_SLOT].healthy is False

        client = _sdk_client(app)
        try:
            assert await client.register() is True  # PUSH exitoso (aterriza en el store)
        finally:
            await client._http_client.aclose()

        # El PUSH no tocó el registry: el slot sigue no-healthy. Registrarse ≠ estar
        # healthy; solo un PULL exitoso lo vuelve healthy.
        assert registry.services[_SLOT].healthy is False, (
            "register() (PUSH) volvió healthy un slot del registry — eso acoplaría los dos "
            "mecanismos que C83 verificó independientes (el registry es PULL, no alta)"
        )
