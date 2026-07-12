"""
Tests for the routine API router (app/api/v1/routine.py).

The router parses ``data/prompt-lists/rutina-diaria.md`` and publishes each
activity as a Google Calendar event (and, optionally, a Prompt OS prompt).
These tests exercise the pure MD/time/timezone helpers directly and drive the
two HTTP endpoints (``GET /routine/today`` and ``POST /routine/sync``) over a
fresh FastAPI app. No real filesystem routine, Google Calendar, DB or network
is touched: ``ROUTINE_FILE`` is redirected to a temp fixture, ``get_google_calendar``
is monkeypatched to a fake, and ``prompt_store`` is an ``AsyncMock`` on app.state.

The GoogleCalendarService itself is already covered by
test_google_calendar_codex.py, so here we only drive the router contract.
"""

import contextlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import routine
from app.core.security import api_key_manager

# A dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-routine", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}

_UNSET = object()

# A routine markdown fixture exercising every parser branch:
# - frontmatter: string, YAML list, true/false booleans, digit->int
# - activity 1: quoted time, digit duration, multiline ">" description with a
#   blank-line paragraph break
# - activity 2: inline (single-line) description, no ">"
# - activity 3: unquoted time (regex extraction) + non-digit duration -> default 30
ROUTINE_MD = """---
name: Test Routine
slug: test-routine
category: routine
is_active: true
draft: false
count: 3
tags: [routine, daily, test]
timezone: Europe/Madrid
---

# Test Routine

## activities

- time: "06:15"
  duration: 15
  summary: "Despertar"
  description: >
    Linea uno del despertar.
    Linea dos con detalle.

    Parrafo tras linea vacia.

- time: "07:00"
  duration: 30
  summary: "Ejercicio"
  description: Texto inline en una sola linea.

- time: 08:00
  duration: notanumber
  summary: "Desayuno"
  description: >
    Desayuno saludable y ligero.
"""


@pytest.fixture
def routine_file(tmp_path: Path, monkeypatch) -> Path:
    """Write the fixture routine and point the router's ROUTINE_FILE at it."""
    path = tmp_path / "rutina-diaria.md"
    path.write_text(ROUTINE_MD, encoding="utf-8")
    monkeypatch.setattr(routine, "ROUTINE_FILE", path)
    return path


def build_app(prompt_store=_UNSET) -> FastAPI:
    """Build a FastAPI app with only the routine router and injected state."""
    app = FastAPI()
    app.include_router(routine.router, prefix="/api/v1")
    if prompt_store is not _UNSET:
        app.state.prompt_store = prompt_store
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def fake_gcal(*, connected=True, event=None, raise_on_create=False) -> MagicMock:
    """Fake GoogleCalendarService: sync is_connected(), async create_event()."""
    g = MagicMock()
    g.is_connected.return_value = connected
    if raise_on_create:
        g.create_event = AsyncMock(side_effect=RuntimeError("gcal boom"))
    else:
        g.create_event = AsyncMock(return_value=event or {"id": "evt-1"})
    return g


# ==================== _parse_routine_md ====================


def test_parse_routine_md_full(routine_file):
    data = routine._parse_routine_md(routine_file)

    fm = data["frontmatter"]
    assert fm["name"] == "Test Routine"
    assert fm["timezone"] == "Europe/Madrid"
    assert fm["is_active"] is True
    assert fm["draft"] is False
    assert fm["count"] == 3
    assert fm["tags"] == ["routine", "daily", "test"]

    acts = data["activities"]
    assert len(acts) == 3

    # Activity 1: quoted time, multiline description with paragraph break
    assert acts[0]["time"] == "06:15"
    assert acts[0]["duration"] == 15
    assert acts[0]["summary"] == "Despertar"
    assert "Linea uno del despertar." in acts[0]["description"]
    assert "Parrafo tras linea vacia." in acts[0]["description"]

    # Activity 2: inline single-line description
    assert acts[1]["time"] == "07:00"
    assert acts[1]["description"] == "Texto inline en una sola linea."

    # Activity 3: unquoted time (regex) + non-digit duration -> default 30
    assert acts[2]["time"] == "08:00"
    assert acts[2]["duration"] == 30


def test_parse_routine_md_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        routine._parse_routine_md(tmp_path / "nope.md")


def test_parse_routine_md_no_frontmatter(tmp_path):
    body = (
        "## activities\n\n"
        '- time: "09:00"\n'
        "  duration: 20\n"
        '  summary: "Solo"\n'
    )
    path = tmp_path / "no-fm.md"
    path.write_text(body, encoding="utf-8")

    data = routine._parse_routine_md(path)
    assert data["frontmatter"] == {}
    assert len(data["activities"]) == 1
    assert data["activities"][0]["summary"] == "Solo"


# ==================== _compute_event_times ====================


def test_compute_event_times():
    start, end = routine._compute_event_times("06:15", 15, "2026-07-12", "-06:00")
    assert start == "2026-07-12T06:15:00-06:00"
    assert end == "2026-07-12T06:30:00-06:00"


# ==================== _tz_offset_for ====================


def test_tz_offset_for_dst_aware():
    # Europe/Madrid: CEST (+02:00) in summer, CET (+01:00) in winter.
    assert routine._tz_offset_for("Europe/Madrid", "2026-07-12") == "+02:00"
    assert routine._tz_offset_for("Europe/Madrid", "2026-01-12") == "+01:00"


def test_tz_offset_for_negative():
    assert routine._tz_offset_for("America/Mexico_City", "2026-07-12") == "-06:00"


def test_tz_offset_for_invalid_falls_back_to_utc():
    assert routine._tz_offset_for("Not/ARealZone", "2026-07-12") == "+00:00"


# ==================== GET /routine/today ====================


async def test_today_ok(routine_file):
    app = build_app()
    async with client_for(app) as c:
        r = await c.get("/api/v1/routine/today", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["timezone"] == "Europe/Madrid"
    assert body["activity_count"] == 3
    assert len(body["activities"]) == 3
    # Each activity is enriched with computed start/end.
    assert all("start" in a and "end" in a for a in body["activities"])


async def test_today_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(routine, "ROUTINE_FILE", tmp_path / "gone.md")
    app = build_app()
    async with client_for(app) as c:
        r = await c.get("/api/v1/routine/today", headers=AUTH)
    assert r.status_code == 404


async def test_today_parse_error(routine_file, monkeypatch):
    def boom(_path):
        raise RuntimeError("parse kaboom")

    monkeypatch.setattr(routine, "_parse_routine_md", boom)
    app = build_app()
    async with client_for(app) as c:
        r = await c.get("/api/v1/routine/today", headers=AUTH)
    assert r.status_code == 500


async def test_today_requires_auth(routine_file):
    app = build_app()
    async with client_for(app) as c:
        r = await c.get("/api/v1/routine/today")
    assert r.status_code in (401, 403)


# ==================== POST /routine/sync ====================


async def test_sync_not_connected(routine_file, monkeypatch):
    monkeypatch.setattr(routine, "get_google_calendar", lambda: fake_gcal(connected=False))
    app = build_app()
    async with client_for(app) as c:
        r = await c.post("/api/v1/routine/sync", headers=AUTH)
    assert r.status_code == 403


async def test_sync_creates_events(routine_file, monkeypatch):
    gcal = fake_gcal(event={"id": "evt-x"})
    monkeypatch.setattr(routine, "get_google_calendar", lambda: gcal)
    app = build_app()
    async with client_for(app) as c:
        r = await c.post("/api/v1/routine/sync", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["events_created"] == 3
    assert body["prompts_created"] == 0
    assert body["errors"] == []
    assert gcal.create_event.await_count == 3


async def test_sync_event_creation_errors(routine_file, monkeypatch):
    monkeypatch.setattr(
        routine, "get_google_calendar", lambda: fake_gcal(raise_on_create=True)
    )
    app = build_app()
    async with client_for(app) as c:
        r = await c.post("/api/v1/routine/sync", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["events_created"] == 0
    assert len(body["errors"]) == 3
    assert all("Failed to create event" in e for e in body["errors"])


async def test_sync_with_prompts(routine_file, monkeypatch):
    gcal = fake_gcal()
    monkeypatch.setattr(routine, "get_google_calendar", lambda: gcal)
    store = AsyncMock()
    app = build_app(prompt_store=store)
    async with client_for(app) as c:
        r = await c.post(
            "/api/v1/routine/sync?create_prompts=true", headers=AUTH
        )
    assert r.status_code == 200
    body = r.json()
    assert body["events_created"] == 3
    assert body["prompts_created"] == 3
    assert store.create_prompt.await_count == 3


async def test_sync_prompts_requested_but_no_store(routine_file, monkeypatch):
    # create_prompts=true but no prompt_store on app.state -> guard skips them.
    monkeypatch.setattr(routine, "get_google_calendar", lambda: fake_gcal())
    app = build_app()  # no prompt_store injected
    async with client_for(app) as c:
        r = await c.post(
            "/api/v1/routine/sync?create_prompts=true", headers=AUTH
        )
    assert r.status_code == 200
    body = r.json()
    assert body["events_created"] == 3
    assert body["prompts_created"] == 0


async def test_sync_prompt_creation_error(routine_file, monkeypatch):
    monkeypatch.setattr(routine, "get_google_calendar", lambda: fake_gcal())
    store = AsyncMock()
    store.create_prompt.side_effect = RuntimeError("store down")
    app = build_app(prompt_store=store)
    async with client_for(app) as c:
        r = await c.post(
            "/api/v1/routine/sync?create_prompts=true", headers=AUTH
        )
    assert r.status_code == 200
    body = r.json()
    assert body["prompts_created"] == 0
    assert any("Failed to create prompt" in e for e in body["errors"])


async def test_sync_honors_date_and_calendar_id(routine_file, monkeypatch):
    gcal = fake_gcal()
    monkeypatch.setattr(routine, "get_google_calendar", lambda: gcal)
    app = build_app()
    async with client_for(app) as c:
        r = await c.post(
            "/api/v1/routine/sync?date=2026-08-01&calendar_id=work", headers=AUTH
        )
    assert r.status_code == 200
    assert r.json()["date"] == "2026-08-01"
    # calendar_id is forwarded to every create_event call.
    for call in gcal.create_event.await_args_list:
        assert call.kwargs["calendar_id"] == "work"
        assert call.kwargs["start"].startswith("2026-08-01T")


async def test_sync_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(routine, "ROUTINE_FILE", tmp_path / "gone.md")
    app = build_app()
    async with client_for(app) as c:
        r = await c.post("/api/v1/routine/sync", headers=AUTH)
    assert r.status_code == 404


async def test_sync_parse_error(routine_file, monkeypatch):
    def boom(_path):
        raise RuntimeError("parse kaboom")

    monkeypatch.setattr(routine, "_parse_routine_md", boom)
    app = build_app()
    async with client_for(app) as c:
        r = await c.post("/api/v1/routine/sync", headers=AUTH)
    assert r.status_code == 500
