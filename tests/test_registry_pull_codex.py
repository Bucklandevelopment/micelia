"""
C90 — Guard EJECUTABLE del REGISTRY PULL: el último tramo del contrato SDK↔registry.

C83 descubrió (y C90 lo cierra) que Micelia tiene DOS mecanismos independientes y que hay
que verificarlos por separado:
  - PUSH: el dominio hace `POST /api/v1/events` (register + heartbeat) → Event Store.
    Pineado ejecutable en C86 (register) y C88 (heartbeat).
  - PULL: el registry SONDEA `{service.url}{health_endpoint}` por su cuenta; si responde
    200 marca el slot `healthy`, extrae `version` del JSON y mide latencia; si la conexión
    se rechaza lo marca `unhealthy` con `error='connection_refused'`.

El PULL se vio A MANO en C83 (`security`→healthy) y C87 (`research`→healthy, `version=None`
por DP-8), pero 90 ciclos nunca lo pinearon ejecutable. Este módulo lo hace ejerciendo el
sondeo DE VERDAD: un servidor HTTP real en un **puerto efímero que el test posee**
(`127.0.0.1:0` → lo asigna el SO), sondeado por el `ServiceRegistry` real con un
`httpx.AsyncClient` real. Se ejerce el round-trip HTTP entero (status, parseo de `version`,
latencia) — lo que un cliente mockeado no puede dar.

HERMETICIDAD (lección C85→C89): NO se sondea `localhost:<puerto de dominio>` (eso dependía
de qué corriera en la máquina — el eje que C89 cerró). Aquí el test **levanta y controla**
el servidor en un puerto que pide al SO; no asume nada del entorno.
"""

import json
import socket
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from app.services.service_registry import ServiceInfo, ServiceRegistry

pytestmark = pytest.mark.asyncio

_SLOT = "research"  # un slot cualquiera del registry; el PULL es agnóstico al nombre


@contextmanager
def _fake_domain(status_code: int, body: dict | None):
    """
    Levanta un servidor HTTP real en 127.0.0.1:<efímero> que responde a CUALQUIER GET con
    `status_code` y `body` (JSON). Cede su base_url. Al salir, lo apaga y libera el puerto.

    El test POSEE este servidor y su puerto (bind a :0 → el SO elige uno libre) — por eso
    es hermético: no depende de que algún dominio real esté corriendo en un puerto fijo.
    """
    payload = json.dumps(body or {}).encode()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (nombre impuesto por BaseHTTPRequestHandler)
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args, **kwargs):  # silenciar el logging a stderr del server
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


def _closed_port() -> int:
    """Puerto de loopback garantizado CERRADO: lo bindea el SO y se suelta acto seguido."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _probe(url: str, endpoint: str = "/health") -> ServiceInfo:
    """Construye un ServiceRegistry REAL con un httpx real, siembra un slot apuntando a
    `url`, ejerce `_check_health` (EL pull) y devuelve el ServiceInfo resultante."""
    async with httpx.AsyncClient() as client:
        registry = ServiceRegistry(client)
        registry.services[_SLOT] = ServiceInfo(name=_SLOT, url=url, enabled=True)
        await registry._check_health(_SLOT, endpoint)
        return registry.services[_SLOT]


# =============================================================================
# El PULL vira el slot a healthy y extrae version + latencia
# =============================================================================


async def test_pull_marks_slot_healthy_and_extracts_version():
    """
    Dominio real sirviendo 200 con `version` → el registry lo marca healthy, guarda la
    versión y una latencia medida. Es lo que C83 vio a mano con cybertools
    (`healthy=True, version=1.0.0`), ahora ejecutable de punta a punta.
    """
    with _fake_domain(200, {"status": "healthy", "version": "1.2.3"}) as url:
        info = await _probe(url)

    assert info.healthy is True
    assert info.version == "1.2.3"
    assert info.error is None
    assert info.latency_ms is not None and info.latency_ms >= 0
    assert info.last_check is not None


async def test_pull_healthy_without_version_is_dp8_shape():
    """
    Dominio real sirviendo 200 SIN `version` (la forma de canela — DP-8, confirmada live en
    C87) → healthy=True pero `version=None`. Ata la observación de C87 a un pin ejecutable:
    el registry sondea con `data.get("version")`, así que un /health sin ese campo es
    healthy igual, solo sin versión. Benigno.
    """
    with _fake_domain(200, {"status": "healthy", "embedding_model": "bge-m3"}) as url:
        info = await _probe(url)

    assert info.healthy is True
    assert info.version is None
    assert info.error is None


async def test_pull_non_200_marks_unhealthy():
    """Un dominio que responde pero NO con 200 (p.ej. 503) → unhealthy (healthy es
    `status_code == 200`). El slot no está sano aunque el socket conteste."""
    with _fake_domain(503, {"status": "degraded"}) as url:
        info = await _probe(url)

    assert info.healthy is False


# =============================================================================
# El PULL contra un puerto muerto → unhealthy con connection_refused
# =============================================================================


async def test_pull_against_dead_port_is_connection_refused():
    """
    Sin nadie sirviendo (puerto cerrado) → el pull captura `httpx.ConnectError` y marca el
    slot `unhealthy` con `error='connection_refused'`. Es el modo de fallo que el warning de
    arranque del registry reporta (DP-15), ahora ejercido de verdad, no mockeado.
    """
    dead_url = f"http://127.0.0.1:{_closed_port()}"
    info = await _probe(dead_url)

    assert info.healthy is False
    assert info.error == "connection_refused"
    assert info.version is None


async def test_pull_recovers_slot_from_unhealthy_to_healthy():
    """
    Transición completa que el monitoreo continuo hace en vivo: un slot que estaba caído
    (connection_refused contra un puerto muerto) vira a `healthy` cuando el dominio empieza a
    responder. Pinea que el PULL RE-evalúa estado, no lo cachea — el 'recovery' que C83 vio
    (security de `connection_refused` a `healthy=True`).
    """
    async with httpx.AsyncClient() as client:
        registry = ServiceRegistry(client)

        # 1) Arranca caído: apuntamos a un puerto muerto.
        dead_url = f"http://127.0.0.1:{_closed_port()}"
        registry.services[_SLOT] = ServiceInfo(name=_SLOT, url=dead_url, enabled=True)
        await registry._check_health(_SLOT, "/health")
        assert registry.services[_SLOT].healthy is False
        assert registry.services[_SLOT].error == "connection_refused"

        # 2) El dominio "arranca": re-apuntamos el slot a un servidor vivo y re-sondeamos.
        with _fake_domain(200, {"version": "9.9.9"}) as url:
            registry.services[_SLOT].url = url
            await registry._check_health(_SLOT, "/health")

        assert registry.services[_SLOT].healthy is True
        assert registry.services[_SLOT].version == "9.9.9"
        assert registry.services[_SLOT].error is None
