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

from starlette.testclient import TestClient

from app.core.config import settings
from app.main import app

_DOMAIN_KEYS = {"health", "research", "education", "security"}


def test_gateway_boots_and_degrades_gracefully_without_infra():
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


def test_gateway_openapi_wired_after_real_boot():
    """El esquema OpenAPI se sirve tras arrancar la app real (todos los routers montados)."""
    with TestClient(app) as client:
        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        paths = schema.json()["paths"]
        # Rutas núcleo que el panel y los dominios consumen deben estar montadas.
        assert "/api/v1/health" in paths
        assert "/api/v1/events" in paths
