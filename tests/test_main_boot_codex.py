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

import httpx
from starlette.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.frangels.orchestrator import get_frangels_orchestrator

# `no_domain_probes` (hermeticidad del lifespan real) vive ahora en conftest.py: lo
# comparten este boot smoke-test (C85) y el guard de registro (C86). Ver su docstring.

_DOMAIN_KEYS = {"health", "research", "education", "security"}


def test_gateway_boots_and_degrades_gracefully_without_infra(no_infra):
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


# ---------------------------------------------------------------------------
# Ramas de ÉXITO-init del lifespan (C113). Los tests de arriba cubren el arranque
# DEGRADADO (sin infra); estos cubren el camino con infra presente y las ramas `else`
# de los flags, que eran el único hueco <80% del árbol (main.py, barrido C112).
# ---------------------------------------------------------------------------


async def test_lifespan_full_init_with_postgres(require_postgres, no_domain_probes):
    """Con PostgreSQL disponible, el lifespan inicializa TODOS los subsistemas (event/user/
    prompt store, prompt agent+executor, md_sync, scheduler, multi-agent) y los apaga limpio.
    Cubre las ramas de éxito (149-234) y de shutdown (243-278) que el arranque degradado no
    toca. `require_postgres` salta sin DB usable; `no_domain_probes` mantiene los sondeos
    herméticos."""
    async with app.router.lifespan_context(app):
        s = app.state
        assert s.event_store is not None
        assert s.user_store is not None
        assert s.prompt_store is not None
        assert s.prompt_agent is not None
        assert s.prompt_executor is not None
        assert s.md_sync is not None
        assert s.scheduler is not None
        assert s.workflow_engine is not None
        assert s.crew_manager is not None
    # tras el shutdown, la tarea de monitoreo del registry quedó cancelada (mismo contrato
    # que el test degradado, ahora por el camino con subsistemas vivos).
    assert app.state.service_registry._monitoring_task.done()


async def test_lifespan_event_store_disabled_takes_else_branch(no_infra, monkeypatch):
    """Con `event_store_enabled=False`, el lifespan toma el `else` (event_store=None sin
    intentar conectar). Cubre la rama 130."""
    monkeypatch.setattr(settings, "event_store_enabled", False, raising=False)
    async with app.router.lifespan_context(app):
        assert app.state.event_store is None


async def test_lifespan_prompt_system_disabled_takes_else_branches(no_infra, monkeypatch):
    """Con `prompt_system_enabled=False`, el lifespan salta el bloque de prompts y toma los
    `else` (prompt_store/agent/executor=None sin intentar). Cubre 186-188."""
    monkeypatch.setattr(settings, "prompt_system_enabled", False, raising=False)
    async with app.router.lifespan_context(app):
        assert app.state.prompt_store is None
        assert app.state.prompt_agent is None
        assert app.state.prompt_executor is None
        assert app.state.md_sync is None


async def test_lifespan_ngrok_enabled_starts_and_stops_tunnel(no_infra, monkeypatch):
    """Con `ngrok_enabled=True`, el lifespan arranca el túnel y loguea la URL (228-230), y el
    shutdown lo para si está conectado (244). Se mockea el servicio de túnel (sin ngrok real)."""
    from unittest.mock import AsyncMock

    import app.main as main_mod

    fake = AsyncMock()
    fake.start = AsyncMock(return_value="https://fake.ngrok.io")
    fake.is_connected = True
    monkeypatch.setattr(main_mod, "get_tunnel_service", lambda: fake)
    monkeypatch.setattr(settings, "ngrok_enabled", True, raising=False)

    async with app.router.lifespan_context(app):
        assert app.state.tunnel_service is fake
    fake.start.assert_awaited_once()
    fake.stop.assert_awaited_once()  # parado en el shutdown (is_connected=True)


async def test_global_exception_handler_returns_500():
    """El handler global de excepciones no manejadas devuelve un 500 con JSON (323-324)."""
    from unittest.mock import MagicMock

    from app.main import global_exception_handler

    resp = await global_exception_handler(MagicMock(), RuntimeError("boom"))
    assert resp.status_code == 500
