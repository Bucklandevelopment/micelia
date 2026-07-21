"""
Tests for the `micelia` CLI (app.cli), C112.

`cli.py` estaba al **0%** (218 stmts) — el mayor hueco de cobertura del árbol, y un
entrypoint REAL de usuario (el comando `micelia`). Cada subcomando: parsea opciones, llama al
gateway por httpx y formatea con Rich; los mapeos de error (non-200, ConnectError→exit 1,
Timeout) no estaban ejercidos.

Se usan `click.testing.CliRunner` (captura la salida Rich y el exit-code) + `respx` (intercepta
el `httpx.AsyncClient` que cada comando crea) — el único borde externo. No se toca red ni gateway.
"""

from unittest.mock import patch

import httpx
import respx
from click.testing import CliRunner

from app.cli import main

_BASE = "http://localhost:8888"


def _run(args, *, url, method="get", response=None, side_effect=None):
    """Invoca el CLI con `respx` mockeando una ruta. `response`=(status, json) o `side_effect`."""
    with respx.mock:
        route = getattr(respx, method)(url)
        if side_effect is not None:
            route.mock(side_effect=side_effect)
        else:
            status, payload = response
            route.mock(return_value=httpx.Response(status, json=payload))
        return CliRunner().invoke(main, args)


# =============================================================================
# status
# =============================================================================

_HEALTH = {
    "status": "healthy", "uptime_seconds": 42.0,
    "services": {"health": {"healthy": True, "latency_ms": 5.0, "url": "http://x"}},
    "resources": {"cpu_percent": 10, "memory": {"available_gb": 8.0, "percent": 50},
                  "disk": {"free_gb": 100.0, "percent": 30}},
}


def test_status_healthy():
    r = _run(["status"], url=f"{_BASE}/api/v1/health/detailed", response=(200, _HEALTH))
    assert r.exit_code == 0
    assert "HEALTHY" in r.output


def test_status_degraded_uses_yellow_branch():
    data = {**_HEALTH, "status": "degraded"}
    r = _run(["status"], url=f"{_BASE}/api/v1/health/detailed", response=(200, data))
    assert r.exit_code == 0
    assert "DEGRADED" in r.output


def test_status_non_200_prints_error():
    r = _run(["status"], url=f"{_BASE}/api/v1/health/detailed", response=(500, {}))
    assert r.exit_code == 0
    assert "Error" in r.output


def test_status_connect_error_exits_1():
    r = _run(["status"], url=f"{_BASE}/api/v1/health/detailed",
             side_effect=httpx.ConnectError("down"))
    assert r.exit_code == 1
    assert "No se puede conectar" in r.output


# =============================================================================
# services
# =============================================================================


def test_services_renders_table():
    data = {"services": {"research": {"enabled": True, "healthy": False, "latency_ms": None,
                                      "url": "http://r", "error": "connection_refused"}}}
    r = _run(["services"], url=f"{_BASE}/api/v1/health/services", response=(200, data))
    assert r.exit_code == 0
    assert "research" in r.output


def test_services_connect_error_exits_1():
    r = _run(["services"], url=f"{_BASE}/api/v1/health/services",
             side_effect=httpx.ConnectError("down"))
    assert r.exit_code == 1


# =============================================================================
# events
# =============================================================================


def test_events_renders_with_category_filter():
    data = {"events": [{"timestamp": "2026-07-21T10:00:00", "category": "system",
                        "event_type": "x.y", "source": "micelia"}], "count": 1}
    r = _run(["events", "--category", "system", "--limit", "5"],
             url=f"{_BASE}/api/v1/events", response=(200, data))
    assert r.exit_code == 0
    assert "system" in r.output and "Total: 1" in r.output


def test_events_503_reports_store_unavailable():
    r = _run(["events"], url=f"{_BASE}/api/v1/events", response=(503, {}))
    assert r.exit_code == 0
    assert "Event Store no disponible" in r.output


def test_events_other_error():
    r = _run(["events"], url=f"{_BASE}/api/v1/events", response=(500, {}))
    assert r.exit_code == 0
    assert "Error" in r.output


# =============================================================================
# ai status — ambas ramas (disponible / no)
# =============================================================================


def test_ai_status_all_available():
    data = {"ollama": {"available": True, "models": ["llama3"]},
            "codking": {"available": True, "cores": ["salud"]},
            "compute_router": {"enabled": True}}
    r = _run(["ai", "status"], url=f"{_BASE}/api/v1/ai/status", response=(200, data))
    assert r.exit_code == 0
    assert "Disponible" in r.output and "Habilitado" in r.output


def test_ai_status_all_unavailable():
    data = {"ollama": {"available": False, "models": []},
            "codking": {"available": False, "cores": []},
            "compute_router": {"enabled": False}}
    r = _run(["ai", "status"], url=f"{_BASE}/api/v1/ai/status", response=(200, data))
    assert r.exit_code == 0
    assert "No disponible" in r.output and "Deshabilitado" in r.output


# =============================================================================
# energy
# =============================================================================


def test_energy_full_details():
    data = {"state": "conserving", "battery_level": 55, "is_charging": False,
            "power_source": "battery", "time_remaining_minutes": 125,
            "solar_available": True, "solar_watts": 12, "is_online": True,
            "recommendations": ["baja el brillo"]}
    r = _run(["energy"], url=f"{_BASE}/api/v1/energy/status", response=(200, data))
    assert r.exit_code == 0
    assert "CONSERVING" in r.output and "baja el brillo" in r.output


def test_energy_connect_error_exits_1():
    r = _run(["energy"], url=f"{_BASE}/api/v1/energy/status",
             side_effect=httpx.ConnectError("down"))
    assert r.exit_code == 1


# =============================================================================
# create-course (POST) — éxito, non-200, timeout, connect
# =============================================================================

_COURSE_URL = f"{_BASE}/api/v1/gateway/pipeline/research-to-course"


def test_create_course_success():
    data = {"papers_analyzed": 12, "synthesis": {"sources": 8},
            "course": {"title": "Redes"}}
    r = _run(["create-course", "redes"], url=_COURSE_URL, method="post", response=(200, data))
    assert r.exit_code == 0
    assert "exitosamente" in r.output and "Redes" in r.output


def test_create_course_non_200():
    r = _run(["create-course", "redes"], url=_COURSE_URL, method="post", response=(500, {}))
    assert r.exit_code == 0
    assert "Error" in r.output


def test_create_course_timeout():
    r = _run(["create-course", "redes"], url=_COURSE_URL, method="post",
             side_effect=httpx.TimeoutException("slow"))
    assert r.exit_code == 0
    assert "Timeout" in r.output


# =============================================================================
# start (uvicorn) + meta
# =============================================================================


def test_start_invokes_uvicorn():
    with patch("uvicorn.run") as run:
        r = CliRunner().invoke(main, ["start", "--host", "127.0.0.1", "--port", "9999"])
    assert r.exit_code == 0
    run.assert_called_once()
    assert run.call_args.kwargs["host"] == "127.0.0.1"
    assert run.call_args.kwargs["port"] == 9999


def test_version_and_help():
    assert CliRunner().invoke(main, ["--version"]).exit_code == 0
    assert CliRunner().invoke(main, ["--help"]).exit_code == 0


# =============================================================================
# ConnectError→exit(1) para los comandos restantes + entrypoint deprecado
# =============================================================================


def test_events_connect_error_exits_1():
    r = _run(["events"], url=f"{_BASE}/api/v1/events", side_effect=httpx.ConnectError("x"))
    assert r.exit_code == 1


def test_ai_status_connect_error_exits_1():
    r = _run(["ai", "status"], url=f"{_BASE}/api/v1/ai/status",
             side_effect=httpx.ConnectError("x"))
    assert r.exit_code == 1


def test_create_course_connect_error_exits_1():
    r = _run(["create-course", "t"], url=_COURSE_URL, method="post",
             side_effect=httpx.ConnectError("x"))
    assert r.exit_code == 1


def test_deprecated_idm_entrypoint_warns():
    """`_main_deprecated` (el CLI `idm` viejo) emite DeprecationWarning y delega en `main`."""
    import warnings

    from app.cli import _main_deprecated

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with patch.object(main, "main", return_value=None):
            try:
                _main_deprecated()
            except SystemExit:
                pass
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
