"""
Tests for the Google Calendar API router (app/api/v1/calendar.py).

The router delegates every operation to the ``GoogleCalendarService`` singleton
returned by ``get_google_calendar`` (already covered by its own service tests).
Here we drive the HTTP contract over a fresh FastAPI app with
``get_google_calendar`` monkeypatched to a ``MagicMock`` — the real singleton is
never constructed and no OAuth flow, token file, or network call happens. Async
methods the router ``await``s are ``AsyncMock``; the synchronous helpers
(``get_status``, ``is_connected``) return plain values.
"""

import contextlib
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import calendar
from app.core.security import api_key_manager

# A dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-calendar", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}

CREATE_PAYLOAD = {
    "calendar_id": "primary",
    "summary": "Standup",
    "start": "2026-07-13T09:00:00+00:00",
    "end": "2026-07-13T09:30:00+00:00",
    "description": "Daily sync",
}


def build_app() -> FastAPI:
    """Build a FastAPI app with only the calendar router mounted."""
    app = FastAPI()
    app.include_router(calendar.router, prefix="/api/v1")
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def fake_gcal(**overrides) -> MagicMock:
    """
    Fake GoogleCalendarService.

    Async methods (awaited by the router) default to ``AsyncMock`` with explicit
    return values; the two synchronous helpers return plain values. ``connected``
    is a convenience kwarg toggling ``is_connected()``; any other kwarg replaces
    the matching attribute (e.g. to inject a ``side_effect``).
    """
    connected = overrides.pop("connected", True)
    g = MagicMock()
    # Synchronous helpers.
    g.is_connected.return_value = connected
    g.get_status.return_value = {
        "installed": True,
        "connected": connected,
        "last_sync": None,
    }
    # Async operations.
    g.authenticate = AsyncMock(return_value={"authorization_url": "https://auth"})
    g.handle_callback = AsyncMock(return_value={"success": True})
    g.list_calendars = AsyncMock(return_value=[{"id": "primary"}, {"id": "work"}])
    g.get_events = AsyncMock(
        return_value=[{"id": "e1", "summary": "Standup"}]
    )
    g.create_event = AsyncMock(return_value={"id": "e-new", "summary": "Standup"})
    g.sync_prompts_from_calendar = AsyncMock(return_value={"created": 2})
    g.sync_results_to_calendar = AsyncMock(return_value={"written": 1})
    g.disconnect = AsyncMock(return_value={"success": True, "disconnected": True})
    for name, value in overrides.items():
        setattr(g, name, value)
    return g


def patch_gcal(monkeypatch, gcal: MagicMock) -> None:
    monkeypatch.setattr(calendar, "get_google_calendar", lambda: gcal)


# ==================== GET /calendar/auth ====================


async def test_auth_ok(monkeypatch):
    gcal = fake_gcal()
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/auth", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"authorization_url": "https://auth"}
    gcal.authenticate.assert_awaited_once()


async def test_auth_runtime_error_501(monkeypatch):
    gcal = fake_gcal(authenticate=AsyncMock(side_effect=RuntimeError("no libs")))
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/auth", headers=AUTH)
    assert resp.status_code == 501
    assert resp.json()["detail"] == "no libs"


async def test_auth_value_error_400(monkeypatch):
    gcal = fake_gcal(authenticate=AsyncMock(side_effect=ValueError("bad config")))
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/auth", headers=AUTH)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "bad config"


async def test_auth_generic_500(monkeypatch):
    gcal = fake_gcal(authenticate=AsyncMock(side_effect=Exception("boom")))
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/auth", headers=AUTH)
    assert resp.status_code == 500
    assert "authorization URL" in resp.json()["detail"]


# ==================== GET /calendar/callback ====================


async def test_callback_ok(monkeypatch):
    gcal = fake_gcal()
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get(
            "/api/v1/calendar/callback", params={"code": "abc123"}, headers=AUTH
        )
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    gcal.handle_callback.assert_awaited_once_with("abc123")


async def test_callback_runtime_error_501(monkeypatch):
    gcal = fake_gcal(handle_callback=AsyncMock(side_effect=RuntimeError("no libs")))
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get(
            "/api/v1/calendar/callback", params={"code": "abc123"}, headers=AUTH
        )
    assert resp.status_code == 501
    assert resp.json()["detail"] == "no libs"


async def test_callback_generic_500(monkeypatch):
    gcal = fake_gcal(handle_callback=AsyncMock(side_effect=Exception("boom")))
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get(
            "/api/v1/calendar/callback", params={"code": "abc123"}, headers=AUTH
        )
    assert resp.status_code == 500
    assert "OAuth2 callback" in resp.json()["detail"]


async def test_callback_missing_code_422(monkeypatch):
    patch_gcal(monkeypatch, fake_gcal())
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/callback", headers=AUTH)
    assert resp.status_code == 422


# ==================== GET /calendar/status ====================


async def test_status_ok(monkeypatch):
    gcal = fake_gcal()
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/status", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["connected"] is True
    gcal.get_status.assert_called_once()


# ==================== GET /calendar/calendars ====================


async def test_list_calendars_not_connected_403(monkeypatch):
    patch_gcal(monkeypatch, fake_gcal(connected=False))
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/calendars", headers=AUTH)
    assert resp.status_code == 403
    assert "not connected" in resp.json()["detail"].lower()


async def test_list_calendars_ok(monkeypatch):
    gcal = fake_gcal()
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/calendars", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert len(body["calendars"]) == 2


async def test_list_calendars_generic_500(monkeypatch):
    gcal = fake_gcal(list_calendars=AsyncMock(side_effect=Exception("boom")))
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/calendars", headers=AUTH)
    assert resp.status_code == 500
    assert "list calendars" in resp.json()["detail"].lower()


# ==================== GET /calendar/events ====================


async def test_get_events_not_connected_403(monkeypatch):
    patch_gcal(monkeypatch, fake_gcal(connected=False))
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/events", headers=AUTH)
    assert resp.status_code == 403


async def test_get_events_default_now(monkeypatch):
    gcal = fake_gcal()
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/events", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["calendar_id"] == "primary"
    # No explicit date → time_min/time_max still populated from now.
    assert body["time_min"] and body["time_max"]
    gcal.get_events.assert_awaited_once()


async def test_get_events_with_date(monkeypatch):
    gcal = fake_gcal()
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get(
            "/api/v1/calendar/events",
            params={"calendar_id": "work", "date": "2026-07-13", "days": 3},
            headers=AUTH,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["calendar_id"] == "work"
    assert body["time_min"].startswith("2026-07-13")


async def test_get_events_bad_date_400(monkeypatch):
    gcal = fake_gcal()
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get(
            "/api/v1/calendar/events",
            params={"date": "13-07-2026"},
            headers=AUTH,
        )
    # The inner 400 must propagate (except HTTPException: raise), not become 500.
    assert resp.status_code == 400
    assert "date format" in resp.json()["detail"].lower()
    gcal.get_events.assert_not_awaited()


async def test_get_events_generic_500(monkeypatch):
    gcal = fake_gcal(get_events=AsyncMock(side_effect=Exception("boom")))
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/events", headers=AUTH)
    assert resp.status_code == 500
    assert "get events" in resp.json()["detail"].lower()


async def test_get_events_days_out_of_range_422(monkeypatch):
    patch_gcal(monkeypatch, fake_gcal())
    async with client_for(build_app()) as ac:
        too_many = await ac.get(
            "/api/v1/calendar/events", params={"days": 91}, headers=AUTH
        )
        too_few = await ac.get(
            "/api/v1/calendar/events", params={"days": 0}, headers=AUTH
        )
    assert too_many.status_code == 422
    assert too_few.status_code == 422


# ==================== POST /calendar/events ====================


async def test_create_event_not_connected_403(monkeypatch):
    patch_gcal(monkeypatch, fake_gcal(connected=False))
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/calendar/events", json=CREATE_PAYLOAD, headers=AUTH
        )
    assert resp.status_code == 403


async def test_create_event_ok(monkeypatch):
    gcal = fake_gcal()
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/calendar/events", json=CREATE_PAYLOAD, headers=AUTH
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["event"]["id"] == "e-new"
    gcal.create_event.assert_awaited_once_with(
        calendar_id="primary",
        summary="Standup",
        start="2026-07-13T09:00:00+00:00",
        end="2026-07-13T09:30:00+00:00",
        description="Daily sync",
    )


async def test_create_event_value_error_400(monkeypatch):
    gcal = fake_gcal(create_event=AsyncMock(side_effect=ValueError("bad time")))
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/calendar/events", json=CREATE_PAYLOAD, headers=AUTH
        )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "bad time"


async def test_create_event_generic_500(monkeypatch):
    gcal = fake_gcal(create_event=AsyncMock(side_effect=Exception("boom")))
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/calendar/events", json=CREATE_PAYLOAD, headers=AUTH
        )
    assert resp.status_code == 500
    assert "create event" in resp.json()["detail"].lower()


async def test_create_event_missing_fields_422(monkeypatch):
    patch_gcal(monkeypatch, fake_gcal())
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/calendar/events",
            json={"summary": "only a title"},  # missing start/end
            headers=AUTH,
        )
    assert resp.status_code == 422


# ==================== POST /calendar/sync ====================


async def test_sync_not_connected_403(monkeypatch):
    patch_gcal(monkeypatch, fake_gcal(connected=False))
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/calendar/sync", headers=AUTH)
    assert resp.status_code == 403


async def test_sync_ok(monkeypatch):
    gcal = fake_gcal()
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/calendar/sync", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["from_calendar"] == {"created": 2}
    assert body["to_calendar"] == {"written": 1}
    gcal.sync_prompts_from_calendar.assert_awaited_once()
    gcal.sync_results_to_calendar.assert_awaited_once()


async def test_sync_generic_500(monkeypatch):
    gcal = fake_gcal(
        sync_prompts_from_calendar=AsyncMock(side_effect=Exception("boom"))
    )
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/calendar/sync", headers=AUTH)
    assert resp.status_code == 500
    assert "sync" in resp.json()["detail"].lower()


# ==================== DELETE /calendar/disconnect ====================


async def test_disconnect_ok(monkeypatch):
    gcal = fake_gcal()
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.delete("/api/v1/calendar/disconnect", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["disconnected"] is True
    gcal.disconnect.assert_awaited_once()


async def test_disconnect_generic_500(monkeypatch):
    gcal = fake_gcal(disconnect=AsyncMock(side_effect=Exception("boom")))
    patch_gcal(monkeypatch, gcal)
    async with client_for(build_app()) as ac:
        resp = await ac.delete("/api/v1/calendar/disconnect", headers=AUTH)
    assert resp.status_code == 500
    assert "disconnect" in resp.json()["detail"].lower()


# ==================== auth ====================


async def test_requires_auth():
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/calendar/status")
    assert resp.status_code in (401, 403)
