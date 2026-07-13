"""
Tests for the Energy API router (app/api/v1/energy.py).

The router (``prefix="/energy"``, ``dependencies=[Depends(verify_auth)]``) exposes
three HTTP endpoints (``/status``, ``/compute-recommendation``, ``/history``), a
WebSocket (``/ws``) and three module-level helpers (``get_battery_status``,
``calculate_state``, ``get_recommendations``).

Conventions (same as the other ``_codex`` router tests):

* **Auth** — a real key is minted once against the shared ``api_key_manager`` and
  sent as ``X-API-Key``; ``verify_auth`` validates it. No ``dependency_overrides``.
* **Mount** — a bare ``FastAPI()`` with only this router, driven by httpx
  ``AsyncClient`` + ``ASGITransport`` (the WebSocket case uses the sync
  ``TestClient`` since httpx cannot speak WS).
* **Isolation** — ``get_battery_status`` reads ``pmset`` via ``subprocess.run``; we
  monkeypatch ``energy.subprocess.run`` (for the helper) or ``energy.get_battery_status``
  (for the endpoints) so nothing shells out. ``settings`` is patched on the module's
  ``settings`` object. ``event_store`` is injected into ``app.state``.

Note on reachable states: the two HTTP endpoints hard-code ``is_online=True`` and
``solar_watts=0.0``, so ``ABUNDANT`` and ``SURVIVAL`` are unreachable through the
HTTP path. Those branches (and all of ``get_recommendations``) are exercised by
calling the helpers directly; for ``/compute-recommendation`` they are reached by
patching ``energy.calculate_state``.
"""

import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from app.api.v1 import energy
from app.api.v1.energy import (
    EnergyState,
    calculate_state,
    get_recommendations,
)
from app.core.security import api_key_manager, verify_auth

# Dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-energy", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}


def build_app(event_store=None) -> FastAPI:
    """Build a FastAPI app with only the energy router; seed app.state.event_store."""
    app = FastAPI()
    app.include_router(energy.router, prefix="/api/v1")
    # /history accesses request.app.state.event_store directly → always set it.
    app.state.event_store = event_store
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def battery(*, level=75, is_charging=True, time_remaining=120, power_source="ac"):
    """Canned battery dict in the shape get_battery_status returns."""
    return {
        "level": level,
        "is_charging": is_charging,
        "time_remaining": time_remaining,
        "power_source": power_source,
    }


# ==================================================================== helpers
# ---- get_battery_status (subprocess.run mocked) --------------------------


def _pmset(monkeypatch, stdout="", *, raise_exc=None):
    """Patch energy.subprocess.run to return canned pmset stdout (or raise)."""
    if raise_exc is not None:
        monkeypatch.setattr(
            energy.subprocess, "run", MagicMock(side_effect=raise_exc)
        )
    else:
        monkeypatch.setattr(
            energy.subprocess,
            "run",
            MagicMock(return_value=MagicMock(stdout=stdout)),
        )


def test_battery_ac_power_with_remaining(monkeypatch):
    _pmset(
        monkeypatch,
        "Now drawing from 'AC Power'\n -InternalBattery-0 92%; charged; 2:30 remaining",
    )
    b = energy.get_battery_status()
    assert b["level"] == 92
    assert b["is_charging"] is True  # "AC Power" present
    assert b["time_remaining"] == 150  # 2*60 + 30
    assert b["power_source"] == "ac"


def test_battery_power_discharging(monkeypatch):
    # Deliberately avoid the substring "charging" (note: the production code treats
    # any "charging" — including "discharging" — as is_charging=True) and "AC Power".
    _pmset(
        monkeypatch,
        "Now drawing from 'Battery Power'\n -InternalBattery-0 45%; 1:20 remaining",
    )
    b = energy.get_battery_status()
    assert b["level"] == 45
    assert b["is_charging"] is False
    assert b["time_remaining"] == 80  # 1*60 + 20
    assert b["power_source"] == "battery"


def test_battery_charging_keyword_unknown_source(monkeypatch):
    # "charging" keyword flips is_charging True; no AC/Battery Power → unknown source,
    # no "remaining" → time -1.
    _pmset(monkeypatch, " -InternalBattery-0 88%; charging; (no estimate)")
    b = energy.get_battery_status()
    assert b["level"] == 88
    assert b["is_charging"] is True
    assert b["time_remaining"] == -1
    assert b["power_source"] == "unknown"


def test_battery_no_percent_defaults(monkeypatch):
    # No digits+% → level fallback 100; no charging markers → False; unknown source.
    _pmset(monkeypatch, "no battery information available")
    b = energy.get_battery_status()
    assert b["level"] == 100
    assert b["is_charging"] is False
    assert b["time_remaining"] == -1
    assert b["power_source"] == "unknown"


def test_battery_exception_fallback(monkeypatch):
    _pmset(monkeypatch, raise_exc=OSError("pmset not found"))
    b = energy.get_battery_status()
    assert b == {
        "level": 100,
        "is_charging": True,
        "time_remaining": -1,
        "power_source": "unknown",
    }


# ---- calculate_state (all five branches, called directly) ----------------


def test_calculate_state_survival():
    # not online and level < 5
    assert calculate_state(battery(level=3, is_charging=False), 0.0, False) == (
        EnergyState.SURVIVAL
    )


def test_calculate_state_critical():
    assert calculate_state(battery(level=15, is_charging=False), 0.0, True) == (
        EnergyState.CRITICAL
    )


def test_calculate_state_conserving():
    assert calculate_state(battery(level=40, is_charging=False), 0.0, True) == (
        EnergyState.CONSERVING
    )


def test_calculate_state_abundant():
    # solar > 50 and level > 80 (and not low/discharging)
    assert calculate_state(battery(level=90, is_charging=True), 60.0, True) == (
        EnergyState.ABUNDANT
    )


def test_calculate_state_normal_default():
    # high level, charging, no solar → falls through to NORMAL
    assert calculate_state(battery(level=70, is_charging=True), 0.0, True) == (
        EnergyState.NORMAL
    )


def test_calculate_state_low_but_charging_is_normal():
    # level < 50 but charging → conserving/critical guards (which require not charging)
    # are skipped → NORMAL.
    assert calculate_state(battery(level=30, is_charging=True), 0.0, True) == (
        EnergyState.NORMAL
    )


# ---- get_recommendations (all five states, called directly) --------------


@pytest.mark.parametrize(
    "state,marker",
    [
        (EnergyState.ABUNDANT, "solar"),
        (EnergyState.NORMAL, "normal"),
        (EnergyState.CONSERVING, "cloud"),
        (EnergyState.CRITICAL, "ALERTA"),
        (EnergyState.SURVIVAL, "SUPERVIVENCIA"),
    ],
)
def test_get_recommendations_each_state(state, marker):
    recs = get_recommendations(state, battery())
    assert isinstance(recs, list) and recs
    assert any(marker.lower() in r.lower() for r in recs)


# ==================================================================== /status


async def test_status_normal(monkeypatch):
    monkeypatch.setattr(
        energy, "get_battery_status", lambda: battery(level=70, is_charging=True)
    )
    monkeypatch.setattr(energy.settings, "solar_api_url", None, raising=False)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/energy/status", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "normal"
    assert body["battery_level"] == 70
    assert body["is_charging"] is True
    assert body["solar_available"] is False
    assert body["solar_watts"] == 0.0
    assert body["is_online"] is True
    assert body["power_source"] == "ac"
    assert isinstance(body["recommendations"], list) and body["recommendations"]


async def test_status_conserving_with_solar_configured(monkeypatch):
    monkeypatch.setattr(
        energy, "get_battery_status", lambda: battery(level=40, is_charging=False)
    )
    monkeypatch.setattr(
        energy.settings, "solar_api_url", "https://solar.local", raising=False
    )
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/energy/status", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "conserving"
    assert body["solar_available"] is True  # solar_api_url is not None


async def test_status_critical(monkeypatch):
    monkeypatch.setattr(
        energy, "get_battery_status", lambda: battery(level=10, is_charging=False)
    )
    monkeypatch.setattr(energy.settings, "solar_api_url", None, raising=False)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/energy/status", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["state"] == "critical"


# ==================================================== /compute-recommendation


async def test_compute_recommendation_normal(monkeypatch):
    monkeypatch.setattr(
        energy, "get_battery_status", lambda: battery(level=70, is_charging=True)
    )
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/energy/compute-recommendation", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["prefer_local"] is True and body["prefer_cloud"] is True
    assert body["max_concurrent_tasks"] == 5
    assert body["allow_heavy_compute"] is True


async def test_compute_recommendation_conserving(monkeypatch):
    monkeypatch.setattr(
        energy, "get_battery_status", lambda: battery(level=40, is_charging=False)
    )
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/energy/compute-recommendation", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["prefer_local"] is False and body["prefer_cloud"] is True
    assert body["max_concurrent_tasks"] == 2
    assert any("40%" in r for r in body["reasoning"])


async def test_compute_recommendation_critical(monkeypatch):
    monkeypatch.setattr(
        energy, "get_battery_status", lambda: battery(level=10, is_charging=False)
    )
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/energy/compute-recommendation", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["max_concurrent_tasks"] == 1
    assert body["allow_heavy_compute"] is False
    assert any("CRÍTICO" in r for r in body["reasoning"])


async def test_compute_recommendation_abundant(monkeypatch):
    # ABUNDANT is unreachable via the battery path (solar hard-coded 0.0) →
    # force the state by patching calculate_state.
    monkeypatch.setattr(energy, "get_battery_status", lambda: battery(level=90))
    monkeypatch.setattr(
        energy, "calculate_state", lambda *_a, **_k: EnergyState.ABUNDANT
    )
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/energy/compute-recommendation", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["max_concurrent_tasks"] == 10
    assert body["allow_heavy_compute"] is True
    assert body["prefer_local"] is True and body["prefer_cloud"] is False


async def test_compute_recommendation_survival(monkeypatch):
    # SURVIVAL is the else branch, also unreachable via HTTP → force it.
    monkeypatch.setattr(energy, "get_battery_status", lambda: battery(level=3))
    monkeypatch.setattr(
        energy, "calculate_state", lambda *_a, **_k: EnergyState.SURVIVAL
    )
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/energy/compute-recommendation", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["max_concurrent_tasks"] == 1
    assert body["prefer_local"] is True and body["prefer_cloud"] is False
    assert any("SUPERVIVENCIA" in r for r in body["reasoning"])


# ==================================================================== /history


async def test_history_no_event_store():
    async with client_for(build_app(event_store=None)) as ac:
        resp = await ac.get("/api/v1/energy/history", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["events"] == []
    assert body["message"] == "Event store not available"


async def test_history_returns_events():
    events = [{"id": 1, "type": "energy"}]
    es = MagicMock()
    es.query_events = AsyncMock(return_value=events)
    async with client_for(build_app(event_store=es)) as ac:
        resp = await ac.get("/api/v1/energy/history?hours=6", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["hours"] == 6
    assert body["events"] == events
    es.query_events.assert_awaited_once()
    kwargs = es.query_events.await_args.kwargs
    assert kwargs["category"] == "system"
    assert kwargs["subcategory"] == "energy"
    assert kwargs["limit"] == 500


# ==================================================================== /ws (WebSocket)


def test_websocket_sends_energy_update(monkeypatch):
    # First loop iteration sends one update; the second call to get_battery_status
    # raises → the endpoint's `except`/`finally` closes cleanly. energy_check_interval
    # set to 0 so the intermediate asyncio.sleep(0) returns immediately.
    #
    # The router's verify_auth dependency uses APIKeyHeader(Security), which FastAPI
    # cannot resolve in a WebSocket scope (it requires a Request) → override it so the
    # endpoint body is reachable. This mirrors the dependency_overrides idiom used by
    # tests/test_auth_endpoints_codex.py.
    monkeypatch.setattr(energy.settings, "energy_check_interval", 0, raising=False)
    monkeypatch.setattr(
        energy,
        "get_battery_status",
        MagicMock(side_effect=[battery(level=77, power_source="ac"), RuntimeError("stop")]),
    )
    app = build_app()
    app.dependency_overrides[verify_auth] = lambda: "test-user"
    with TestClient(app).websocket_connect("/api/v1/energy/ws") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "energy_update"
    assert msg["data"]["battery_level"] == 77
    assert msg["data"]["power_source"] == "ac"
    assert msg["data"]["state"] in {s.value for s in EnergyState}
    assert "timestamp" in msg


# ==================================================================== auth


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/energy/status",
        "/api/v1/energy/compute-recommendation",
        "/api/v1/energy/history",
    ],
)
async def test_requires_auth(path):
    async with client_for(build_app()) as ac:
        resp = await ac.get(path)
    assert resp.status_code in (401, 403)
