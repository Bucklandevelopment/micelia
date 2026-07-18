"""Boot smoke-test del gateway REAL (`app.main:app`) — Ciclo 69.

Todo el resto de la suite corre contra la app SINTÉTICA de `conftest._build_test_app`
(routers sueltos, estado mockeado, SIN lifespan — ver el comentario "no lifespan
needed for tests"). Es decir: hasta hoy NINGÚN test arrancaba `app.main:app` a través
de su `lifespan` real, y `app/main.py` estaba al 0% de cobertura (186/186 stmts sin
tocar). El único chequeo de arrancabilidad que había era manual (`run-local.sh start`
+ `curl`), no ejecutable en CI.

Este test conduce el `lifespan` REAL con TODA la infra ausente (sin Postgres, Redis
ni dominios) y pinea el CONTRATO de arranque local (prioridad #5 del protocolo diario):

1. El arranque COMPLETA — la degradación con warning de Event/Prompt/User Store NO
   debe convertirse en un `Application startup failed. Exiting.` (regresión real que
   el log histórico `logs/micelia-gateway.log` muestra que YA ocurrió antes de existir
   la degradación graciosa). Ningún unit-test lo cazaba porque ninguno bootea el lifespan.
2. Los endpoints públicos (`/`, `/api/v1/health`, `/api/v1/health/services`) responden.
3. `app.state` refleja la degradación: stores en None, pero http_client / event_bus /
   service_registry presentes (el gateway sirve aunque los subsistemas opcionales caigan).
4. El shutdown CANCELA la tarea de monitoreo del registry (guard de regresión del
   `fix(main)` de C69: `discover_services` arranca `_continuous_monitoring` como tarea
   de fondo y el cleanup debe pararla con `stop_monitoring()` antes de cerrar el
   http_client que ese loop usa). Mutación: quitar el `stop_monitoring()` del lifespan
   deja `_monitoring_task.done()` en False y este test falla nombrando el contrato.

Método = arrancar el sistema de verdad, no leer el código: replica lo que hace
`run-local.sh` pero in-process y determinista, sin ocupar el puerto 8888 ni RAM extra.
"""

import socket

import httpx
import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.frangels.orchestrator import get_frangels_orchestrator

_DOMAIN_KEYS = {"health", "research", "education", "security"}

# URLs de dominio que `discover_services` sondea al arrancar el lifespan. Son las que
# el registry recorre; su default es `localhost:<puerto de dominio>` (config.py).
_PROBED_URL_ATTRS = (
    "health_service_url",
    "research_service_url",
    "education_service_url",
    "security_service_url",
    "ollama_code_url",
    "imperio_lab_url",
)


def _closed_loopback_port() -> int:
    """Puerto de loopback garantizado CERRADO: lo bindea el SO y se suelta acto seguido."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def no_domain_probes(monkeypatch):
    """
    Hermeticidad de arranque (C85). ESTE es el único fichero que arranca el lifespan
    REAL (`app.main:app` vía `TestClient`), y arrancarlo dispara `discover_services`,
    que **sondea de verdad** los puertos de los dominios (localhost:8080/3690/5050/
    8000/8891). Sin fijar el entorno, el resultado de ese sondeo depende de qué haya
    corriendo en la máquina del dev — no de lo que el test controla.

    Esto tenía dos caras:
      * `test_gateway...without_infra` ASSERTA `healthy is False` → con cualquier
        dominio arriba se ponía ROJO (lo cazó C85: cybertools entró en el launcher, así
        que `run-ecosystem.sh start` + `make verify` lo disparaba). Correctness.
      * los otros dos tests de lifespan NO assertan salud, así que no se ponían rojos,
        pero igualmente FIRABAN sockets reales contra esos puertos en cada corrida —
        latencia y una superficie de cuelgue (un puerto que acepta y no responde).

    Esta fixture cierra las dos: apunta TODOS los sondeos a un puerto de loopback
    garantizado cerrado → `connection_refused` determinista. Se conserva el sondeo REAL
    (no se mockea el cliente http): se fija el ENTORNO, no el comportamiento. Aplicada a
    los 3 tests que bootean el lifespan → el fichero deja de tocar la red por completo.
    """
    closed = _closed_loopback_port()
    for attr in _PROBED_URL_ATTRS:
        monkeypatch.setattr(settings, attr, f"http://127.0.0.1:{closed}", raising=False)


def test_gateway_boots_and_degrades_gracefully_without_infra(no_domain_probes):
    """El gateway real arranca, sirve y apaga limpio con toda la infra ausente."""
    # `with TestClient(...)` ejecuta el lifespan REAL: startup al entrar, shutdown al salir.
    with TestClient(app) as client:
        # (1) Arranque completado sin excepción → los endpoints responden.
        # (2) Root: contrato de identidad + flags de servicios habilitados (config, no health).
        root = client.get("/")
        assert root.status_code == 200
        body = root.json()
        assert body["name"] == "Micelia"
        assert body["version"] == "0.1.0"
        assert set(body["services"]) == _DOMAIN_KEYS
        # `/`.services refleja los flags *_service_enabled (habilitado), no la salud viva.
        assert body["services"]["health"] == settings.health_service_enabled
        assert body["services"]["research"] == settings.research_service_enabled
        assert body["services"]["education"] == settings.education_service_enabled
        assert body["services"]["security"] == settings.security_service_enabled

        # Health público responde ok aunque los dominios estén caídos.
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        # El registry expone los dominios; sin infra, ninguno está healthy.
        services = client.get("/api/v1/health/services")
        assert services.status_code == 200
        reg_body = services.json()["services"]
        assert _DOMAIN_KEYS <= set(reg_body)
        for name in _DOMAIN_KEYS:
            assert reg_body[name]["healthy"] is False

        # (3) Degradación en app.state: stores opcionales en None, núcleo presente.
        assert app.state.event_store is None
        assert app.state.prompt_store is None
        assert app.state.user_store is None
        assert app.state.http_client is not None
        assert app.state.event_bus is not None
        registry = app.state.service_registry
        assert registry is not None
        # El monitoreo de fondo está vivo mientras el gateway corre.
        assert registry._monitoring_task is not None
        assert not registry._monitoring_task.done()

    # (4) Tras el shutdown, el fix(main) de C69 cancela la tarea de monitoreo.
    assert registry._monitoring_task.done()


def test_frangels_orchestrator_client_closed_after_shutdown(no_domain_probes):
    """El shutdown del lifespan cierra el cliente httpx propio del orquestador Frangels.

    Guard de regresión del `fix(main)` de C70. `FrangelsOrchestrator._get_client`
    cachea un `httpx.AsyncClient` en el singleton (aparte del http_client compartido
    del gateway) que ningún cleanup cerraba → transport/pool sin liberar en cada
    shutdown/reload, atados a un event loop ya cerrado (misma clase de bug que la
    tarea de monitoreo huérfana de C69).

    El cliente es LAZY (solo existe si algún endpoint de frangels lo ejercitó), así que
    lo forzamos con `_get_client()` mientras el gateway corre, y verificamos que el
    shutdown lo deja cerrado. Mutación: quitar `await frangels_orch.aclose()` del
    lifespan deja `is_closed` en False y este test falla nombrando el contrato.
    """
    orch = get_frangels_orchestrator()
    # Simular el cliente perezoso que un `.chat()`/`.test()` de frangels dejaría
    # cacheado en el singleton (`_get_client` hace exactamente esta asignación).
    # Es un cliente idle (sin request emitido), como el que sobrevive a un shutdown.
    orch._client = httpx.AsyncClient(timeout=60)
    assert not orch._client.is_closed

    with TestClient(app):
        # Mientras el gateway corre, el cliente propio del orquestador sigue abierto.
        assert not orch._client.is_closed

    # Tras el shutdown, el `aclose()` del lifespan (fix C70) lo deja cerrado.
    assert orch._client.is_closed


def test_gateway_openapi_wired_after_real_boot(no_domain_probes):
    """El esquema OpenAPI se sirve tras arrancar la app real (todos los routers montados)."""
    with TestClient(app) as client:
        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        paths = schema.json()["paths"]
        # Rutas núcleo que el panel y los dominios consumen deben estar montadas.
        assert "/api/v1/health" in paths
        assert "/api/v1/events" in paths
