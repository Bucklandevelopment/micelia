"""
Tests for ServiceRegistry: health discovery + continuous monitoring.

The only external boundary is the injected httpx.AsyncClient, so everything
runs deterministically with an AsyncMock — no network, no infra.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.api.v1.health import ServiceStatus
from app.services.service_registry import ServiceInfo, ServiceRegistry


def _resp(status=200, payload=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    return r


@pytest.fixture
def client():
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def registry(client):
    reg = ServiceRegistry(client)
    reg.services["health"] = ServiceInfo(
        name="health", url="http://svc:8080", enabled=True
    )
    return reg


# --------------------------------------------------------------------------
# _check_health
# --------------------------------------------------------------------------

async def test_check_health_ok_sets_healthy_and_version(registry):
    registry.client.get.return_value = _resp(200, {"version": "1.2.3"})
    ok = await registry._check_health("health", "/health")
    assert ok is True
    s = registry.services["health"]
    assert s.healthy is True
    assert s.version == "1.2.3"
    assert s.error is None
    assert s.latency_ms is not None
    assert s.last_check is not None


async def test_check_health_non_200_marks_unhealthy(registry):
    registry.client.get.return_value = _resp(503)
    ok = await registry._check_health("health", "/health")
    assert ok is True  # got a response, but service is unhealthy
    assert registry.services["health"].healthy is False


async def test_check_health_bad_json_is_ignored(registry):
    r = _resp(200)
    r.json.side_effect = ValueError("bad json")
    registry.client.get.return_value = r
    ok = await registry._check_health("health", "/health")
    assert ok is True
    assert registry.services["health"].healthy is True
    assert registry.services["health"].version is None


async def test_check_health_timeout(registry):
    registry.client.get.side_effect = httpx.TimeoutException("t")
    ok = await registry._check_health("health", "/health")
    assert ok is False
    assert registry.services["health"].error == "timeout"
    assert registry.services["health"].healthy is False


async def test_check_health_connect_error(registry):
    registry.client.get.side_effect = httpx.ConnectError("c")
    ok = await registry._check_health("health", "/health")
    assert ok is False
    assert registry.services["health"].error == "connection_refused"


async def test_check_health_generic_exception(registry):
    registry.client.get.side_effect = RuntimeError("boom")
    ok = await registry._check_health("health", "/health")
    assert ok is False
    assert "boom" in registry.services["health"].error


async def test_check_health_unknown_service_returns_false(registry):
    assert await registry._check_health("nope", "/health") is False


async def test_check_health_recovery_path(registry):
    # was unhealthy -> becomes healthy with log_on_fail True hits the recovery branch
    registry.services["health"].healthy = False
    registry.client.get.return_value = _resp(200, {})
    ok = await registry._check_health("health", "/health", log_on_fail=True)
    assert ok is True
    assert registry.services["health"].healthy is True


# Contrato de version del health-body, auditado leyendo el handler REAL de cada
# dominio hermano (Ciclo 67, 2026-07-15). `_check_health` extrae la versión con
# `data.get("version")` (service_registry.py:184): los dominios que la emiten a
# nivel superior la exponen en el panel; canela NO la emite -> queda None por
# lectura defensiva (DP-8). Cada cuerpo reproduce los campos reales del handler
# para que un cambio de contrato en un dominio rompa este pin. Los tests previos
# cubren version-presente (`..._ok_sets_healthy_and_version`), json-inválido
# (`..._bad_json_is_ignored`) y propagación None en check_service; NINGUNO pinea
# el caso canela real (200 con JSON válido que SIMPLEMENTE OMITE `version`) en el
# borde de _check_health -> esta parametrización lo cierra.
_AUDITED_HEALTH_BODIES = {
    # biohack-app/backend/main.py:217 -> "version": "0.1.0" a nivel superior
    "biohack": (
        {
            "status": "healthy",
            "version": "0.1.0",
            "service": "biohack-app",
            "capabilities": ["healthkit-import", "bio-savant-ai"],
            "dependencies": {"database": "connected"},
        },
        "0.1.0",
    ),
    # cybertools/src/scanet/api.py:139 -> "version": SERVICE_VERSION
    "cybertools": (
        {
            "status": "ok",
            "service": "scanet",
            "version": "0.1.0",
            "timestamp": "2026-07-15T00:00:00Z",
            "dependencies": {},
        },
        "0.1.0",
    ),
    # ideacursi-tool/backend/src/health/health.controller.js:73 -> version: '0.1.0'
    "ideacursi": (
        {
            "status": "healthy",
            "version": "0.1.0",
            "service": "ideacursi-tool",
            "category": "education",
            "port": 5050,
            "capabilities": ["courses", "quizzes"],
            "dependencies": {},
        },
        "0.1.0",
    ),
    # canela-molida/app/main.py:540 -> return SIN "version" a nivel superior (DP-8)
    "canela": (
        {
            "status": "healthy",
            "embedding_model": "BAAI/bge-m3",
            "embedding_cache": {"hits": 1500, "misses": 50, "size": 1550},
            "vectorstore": {"num_documents": 5000},
        },
        None,
    ),
}


@pytest.mark.parametrize("domain", list(_AUDITED_HEALTH_BODIES))
async def test_check_health_version_matches_audited_domain_body(registry, domain):
    body, expected = _AUDITED_HEALTH_BODIES[domain]
    registry.client.get.return_value = _resp(200, body)
    ok = await registry._check_health("health", "/health")
    assert ok is True
    assert registry.services["health"].healthy is True
    # Mutación: si canela empieza a emitir `version`, o si alguien "arregla"
    # _check_health para defaultear la versión ausente (p.ej. get("version",
    # "unknown")), este pin rompe y obliga a re-auditar el handler del dominio
    # ANTES de cambiar la expectativa (mismo protocolo que el pin de
    # HEALTH_ENDPOINTS de C66).
    assert registry.services["health"].version == expected, (
        f"El contrato de `version` del health-body de {domain} divergió del "
        f"auditado (Ciclo 67); re-verifica su handler (ver comentario con "
        f"file:line) antes de tocar este pin."
    )


# --------------------------------------------------------------------------
# _log_failure (static, level-selection branches)
# --------------------------------------------------------------------------

def test_log_failure_all_branches():
    # silenced (startup consolidation)
    ServiceRegistry._log_failure("s", "timeout", was_healthy=False, log_on_fail=False)
    # healthy -> unhealthy transition (WARNING)
    ServiceRegistry._log_failure("s", "timeout", was_healthy=True, log_on_fail=True)
    # still down (DEBUG)
    ServiceRegistry._log_failure("s", "timeout", was_healthy=False, log_on_fail=True)


# --------------------------------------------------------------------------
# check_service / getters
# --------------------------------------------------------------------------

async def test_check_service_found(registry):
    registry.services["health"].healthy = True
    registry.services["health"].latency_ms = 12.5
    # La versión que _check_health captura del body del dominio debe llegar al
    # ServiceStatus (antes se quedaba en ServiceInfo y no la exponía nadie).
    registry.services["health"].version = "1.2.3"
    status = await registry.check_service("health")
    assert isinstance(status, ServiceStatus)
    assert status.name == "health"
    assert status.healthy is True
    assert status.latency_ms == 12.5
    assert status.version == "1.2.3"


async def test_check_service_version_defaults_none_when_domain_omits_it(registry):
    # canela (/health) no emite `version` a nivel superior → _check_health deja
    # ServiceInfo.version en None y check_service debe propagar None sin romper.
    registry.services["health"].version = None
    status = await registry.check_service("health")
    assert status.version is None


async def test_check_service_not_found(registry):
    status = await registry.check_service("ghost")
    assert status.healthy is False
    assert status.error == "Service not found"
    assert status.url == "unknown"


def test_get_all_and_healthy_services(registry):
    registry.services["a"] = ServiceInfo(name="a", url="u", enabled=True, healthy=True)
    registry.services["b"] = ServiceInfo(name="b", url="u", enabled=True, healthy=False)
    assert {"health", "a", "b"} <= set(registry.get_all_services())
    healthy = registry.get_healthy_services()
    assert "a" in healthy
    assert "b" not in healthy


# --------------------------------------------------------------------------
# monitoring lifecycle
# --------------------------------------------------------------------------

async def test_stop_monitoring_without_task_is_noop(registry):
    await registry.stop_monitoring()  # should not raise


async def test_stop_monitoring_cancels_running_task(registry):
    async def _loop():
        await asyncio.sleep(3600)

    registry._monitoring_task = asyncio.create_task(_loop())
    await asyncio.sleep(0)  # let the task start
    await registry.stop_monitoring()
    assert registry._monitoring_task.done()


async def test_discover_services_registers_all_and_starts_monitoring(client):
    client.get.return_value = _resp(200, {"version": "9"})
    reg = ServiceRegistry(client)
    try:
        await reg.discover_services()
        assert set(reg.services) == {
            "health", "research", "education", "security", "devtools", "testlab"
        }
        assert reg._monitoring_task is not None
    finally:
        await reg.stop_monitoring()


async def test_health_endpoints_cover_every_registered_service(client):
    # Invariante de coherencia: HEALTH_ENDPOINTS es la fuente ÚNICA del endpoint
    # de health y la consumen discover_services (chequeo inicial) y
    # _continuous_monitoring (monitoreo periódico). Si un futuro dominio se añade
    # a discover_services pero NO a HEALTH_ENDPOINTS, el monitoreo continuo caería
    # al fallback "/health" en silencio -> este test lo caza antes.
    client.get.return_value = _resp(200, {"version": "1"})
    reg = ServiceRegistry(client)
    try:
        await reg.discover_services()
        assert set(reg.services) <= set(ServiceRegistry.HEALTH_ENDPOINTS), (
            "Todo servicio registrado debe tener endpoint en HEALTH_ENDPOINTS"
        )
    finally:
        await reg.stop_monitoring()


def test_health_endpoints_match_audited_domain_contracts():
    # Tripwire de coherencia inter-proyecto (auditado Ciclo 66, 2026-07-15
    # leyendo el handler REAL de cada dominio hermano). El test anterior solo
    # garantiza que cada servicio TIENE endpoint; este PINEA el valor exacto de
    # la ruta que sirve cada dominio. Si alguien edita HEALTH_ENDPOINTS sin
    # re-verificar el dominio, el healthcheck del gateway sondearía una ruta que
    # el dominio no sirve (404 -> "unhealthy" silencioso, como el drift de
    # puertos que cerró C65). Rutas ancladas al código del dominio:
    #   - health   (biohack-app):   /api/v1/service-health
    #                               (biohack-app/backend/main.py:209 @app.get)
    #   - research (canela-molida): /health
    #                               (canela-molida/app/main.py:505 @app.get)
    #   - education (ideacursi-tool): /api/health
    #                               (@Controller('health')+@Get() en
    #                                backend/src/health/health.controller.js
    #                                bajo setGlobalPrefix('api') en main.js:65)
    #   - security (cybertools):    /health
    #                               (cybertools/src/scanet/api.py:127 @app.get)
    # devtools/testlab: default "/health" (servicios feature-flagged, no montados).
    assert ServiceRegistry.HEALTH_ENDPOINTS == {
        "health": "/api/v1/service-health",
        "research": "/health",
        "education": "/api/health",
        "security": "/health",
        "devtools": "/health",
        "testlab": "/health",
    }, (
        "HEALTH_ENDPOINTS divergió del contrato auditado; re-verifica el handler "
        "de health del dominio afectado ANTES de actualizar este pin (ver "
        "docstring: file:line de cada dominio)."
    )


async def test_discover_services_unhealthy_only_health_hint(client, monkeypatch):
    # Enable ONLY the 'health' domain and make it fail -> hits the consolidated
    # unhealthy-summary branch with the "make docker-health" hint.
    from app.services import service_registry as sr

    for attr in (
        "research_service_enabled", "education_service_enabled",
        "security_service_enabled", "ollama_code_enabled", "imperio_lab_enabled",
    ):
        monkeypatch.setattr(sr.settings, attr, False, raising=False)
    monkeypatch.setattr(sr.settings, "health_service_enabled", True, raising=False)
    client.get.return_value = _resp(503)

    reg = ServiceRegistry(client)
    try:
        await reg.discover_services()
        assert reg.services["health"].enabled is True
        assert reg.services["health"].healthy is False
    finally:
        await reg.stop_monitoring()


async def test_continuous_monitoring_runs_one_cycle_then_cancels(registry, monkeypatch):
    from app.services import service_registry as sr

    registry.services["health"].enabled = True
    registry.client.get.return_value = _resp(200, {})

    calls = {"n": 0}

    async def fake_sleep(_seconds):
        calls["n"] += 1
        if calls["n"] >= 2:  # break out after one full health-check cycle
            raise asyncio.CancelledError

    monkeypatch.setattr(sr.asyncio, "sleep", fake_sleep)
    await registry._continuous_monitoring()

    assert registry.client.get.await_count >= 1  # health check ran once


async def test_discover_services_unhealthy_multiple_hint_docker_full(client, monkeypatch):
    # Varios dominios habilitados y TODOS caídos -> el conjunto unhealthy != {"health"}
    # -> se toma la rama `else` con el hint "make docker-full" (línea 112).
    from app.services import service_registry as sr

    for attr in (
        "research_service_enabled", "education_service_enabled",
        "security_service_enabled", "ollama_code_enabled", "imperio_lab_enabled",
        "health_service_enabled",
    ):
        monkeypatch.setattr(sr.settings, attr, True, raising=False)
    client.get.return_value = _resp(503)  # response received, but unhealthy

    reg = ServiceRegistry(client)
    try:
        await reg.discover_services()
        unhealthy = {s.name for s in reg.services.values() if s.enabled and not s.healthy}
        assert unhealthy != {"health"}
        assert len(unhealthy) > 1  # forces the docker-full branch, not docker-health
    finally:
        await reg.stop_monitoring()


async def test_continuous_monitoring_generic_exception_is_logged(registry, monkeypatch):
    # Una iteración del loop lanza una excepción NO-Cancelled -> rama `except Exception`
    # (252-254): log.error + backoff `await asyncio.sleep(5)`; la siguiente vuelta
    # recibe CancelledError y sale limpiamente.
    from app.services import service_registry as sr

    registry.services["health"].enabled = True
    calls = {"n": 0}

    async def fake_sleep(_seconds):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("monitor boom")  # top-of-loop sleep -> except 252
        if calls["n"] == 2:
            return  # the backoff sleep(5) at line 254
        raise asyncio.CancelledError  # next cycle -> clean break (250-251)

    monkeypatch.setattr(sr.asyncio, "sleep", fake_sleep)
    await registry._continuous_monitoring()  # must not raise
    assert calls["n"] >= 3
