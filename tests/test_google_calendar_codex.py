"""
Tests for GoogleCalendarService (app.services.google_calendar).

External boundaries, all isolated here (no network, no DB, no real Google libs):

  - **Google client libs** (``Flow``, ``Credentials``, ``build``) are imported under
    a ``try/except`` guarded by ``GOOGLE_LIBS_AVAILABLE``. They are NOT installed in
    this environment (flag is ``False``), so the "libs unavailable" guards test
    directly, and the auth happy-paths run with ``GOOGLE_LIBS_AVAILABLE`` monkeypatched
    to ``True`` plus fakes injected into ``gc.Flow`` / ``gc.Credentials`` / ``gc.build``.
  - **``TOKEN_PATH``** (``./data/google_token.json``) is redirected to ``tmp_path`` by
    an autouse fixture so nothing touches the real workspace (``disconnect`` unlinks it).
  - **The Google API ``service``** is a ``MagicMock`` whose chained
    ``calendarList()/events().list()/insert().execute`` return controlled dicts;
    ``asyncio.to_thread(fn)`` just runs the mock callable and returns its value.
  - **``PromptStore``** (imported lazily inside the sync methods) is patched at
    ``app.services.prompt_store.PromptStore`` with ``AsyncMock`` methods.

``asyncio_mode = auto`` (pyproject) → ``async def test_*`` needs no marker.

Covers:
  - authenticate (libs off, missing creds, happy url+state, except)
  - handle_callback (libs off, happy write-token+build+success with expiry None/set, except)
  - is_connected (creds cached, no file, file->_load_credentials, _load raises->False)
  - _load_credentials (libs off no-op, no file no-op, happy build, refresh branch via
    stubbed google.auth.transport.requests, load error -> reset)
  - _save_credentials (no creds no-op, happy write, write error swallowed)
  - _ensure_service (present -> ok, not connected -> RuntimeError)
  - list_calendars (populated + missing defaults, except)
  - get_events (default window, explicit window, date vs dateTime, except)
  - create_event (missing summary/start/end -> ValueError, happy, except)
  - sync_prompts_from_calendar ([PROMPT] create, no-tag skip, already-synced skip,
    empty content -> description, scheduled_at parse ok/bad, except, store.close in finally)
  - sync_results_to_calendar (create+mark, no output skip, already-synced skip,
    no completed_at skip, bad completed_at -> now, except)
  - disconnect (with/without token file, state cleared, unlink error re-raised)
  - get_status (shape; last_sync None/set)
  - get_google_calendar singleton
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.google_calendar as gc
from app.services.google_calendar import GoogleCalendarService, get_google_calendar

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Redirect TOKEN_PATH to a temp file and reset the module singleton.

    Keeps every test hermetic: no real ``./data/google_token.json`` is read or
    written, and ``get_google_calendar`` starts from a clean slate each time.
    """
    monkeypatch.setattr(gc, "TOKEN_PATH", tmp_path / "google_token.json")
    gc._google_calendar = None
    yield
    gc._google_calendar = None


_UNSET = object()


class _FakeCreds:
    """Minimal stand-in for google.oauth2.credentials.Credentials."""

    def __init__(
        self,
        token="tok",
        refresh_token="rtok",
        token_uri="uri",
        client_id="cid",
        client_secret="sec",
        scopes=_UNSET,
        expiry=None,
        expired=False,
    ):
        self.token = token
        self.refresh_token = refresh_token
        self.token_uri = token_uri
        self.client_id = client_id
        self.client_secret = client_secret
        # Explicit ``scopes=None`` is preserved so the SCOPES fallback is exercised.
        self.scopes = ["s1"] if scopes is _UNSET else scopes
        self.expiry = expiry
        self.expired = expired
        self.refreshed = False

    def refresh(self, request):  # pragma: no cover - exercised via refresh branch
        self.refreshed = True
        self.token = "refreshed-token"


def _svc(calendars=None, events=None, created=None):
    """Build a MagicMock Google API service with configured chained returns."""
    svc = MagicMock()
    if calendars is not None:
        svc.calendarList.return_value.list.return_value.execute.return_value = {
            "items": calendars
        }
    if events is not None:
        svc.events.return_value.list.return_value.execute.return_value = {"items": events}
    if created is not None:
        svc.events.return_value.insert.return_value.execute.return_value = created
    return svc


def _enable_libs(monkeypatch, flow=None, creds_factory=None, build_ret=None):
    """Turn on GOOGLE_LIBS_AVAILABLE and inject fake Flow/Credentials/build."""
    monkeypatch.setattr(gc, "GOOGLE_LIBS_AVAILABLE", True)
    if flow is not None:
        flow_mock = MagicMock()
        flow_mock.from_client_config.return_value = flow
        monkeypatch.setattr(gc, "Flow", flow_mock)
    if creds_factory is not None:
        monkeypatch.setattr(gc, "Credentials", creds_factory)
    if build_ret is not None:
        monkeypatch.setattr(gc, "build", MagicMock(return_value=build_ret))


def _set_google_creds(monkeypatch, cid="cid", secret="sec"):
    monkeypatch.setattr(gc.settings, "google_client_id", cid, raising=False)
    monkeypatch.setattr(gc.settings, "google_client_secret", secret, raising=False)


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------


class TestAuthenticate:
    async def test_libs_unavailable_raises(self, monkeypatch):
        monkeypatch.setattr(gc, "GOOGLE_LIBS_AVAILABLE", False)
        with pytest.raises(RuntimeError, match="not installed"):
            await GoogleCalendarService().authenticate()

    async def test_missing_credentials_raises(self, monkeypatch):
        monkeypatch.setattr(gc, "GOOGLE_LIBS_AVAILABLE", True)
        monkeypatch.setattr(gc.settings, "google_client_id", None, raising=False)
        monkeypatch.setattr(gc.settings, "google_client_secret", None, raising=False)
        with pytest.raises(ValueError, match="not configured"):
            await GoogleCalendarService().authenticate()

    async def test_happy_returns_url_and_state(self, monkeypatch):
        fake_flow = MagicMock()
        fake_flow.authorization_url.return_value = ("http://auth.example/x", "st8")
        _enable_libs(monkeypatch, flow=fake_flow)
        _set_google_creds(monkeypatch)

        result = await GoogleCalendarService().authenticate()

        assert result == {"authorization_url": "http://auth.example/x", "state": "st8"}
        assert fake_flow.redirect_uri == gc.REDIRECT_URI

    async def test_flow_error_reraised(self, monkeypatch):
        _enable_libs(monkeypatch, flow=MagicMock())
        _set_google_creds(monkeypatch)
        gc.Flow.from_client_config.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            await GoogleCalendarService().authenticate()


# ---------------------------------------------------------------------------
# handle_callback
# ---------------------------------------------------------------------------


class TestHandleCallback:
    async def test_libs_unavailable_raises(self, monkeypatch):
        monkeypatch.setattr(gc, "GOOGLE_LIBS_AVAILABLE", False)
        with pytest.raises(RuntimeError, match="not installed"):
            await GoogleCalendarService().handle_callback("code")

    async def test_happy_writes_token_and_builds_service(self, monkeypatch):
        creds = _FakeCreds(token="tk", expiry=None)
        fake_flow = MagicMock()
        fake_flow.credentials = creds
        service = MagicMock()
        _enable_libs(monkeypatch, flow=fake_flow, build_ret=service)
        _set_google_creds(monkeypatch)

        svc = GoogleCalendarService()
        result = await svc.handle_callback("the-code")

        assert result["success"] is True
        fake_flow.fetch_token.assert_called_once_with(code="the-code")
        assert svc._service is service
        assert svc._credentials is creds
        saved = json.loads(gc.TOKEN_PATH.read_text())
        assert saved["token"] == "tk"
        assert saved["expiry"] is None

    async def test_happy_serialises_expiry(self, monkeypatch):
        expiry = datetime(2030, 1, 1, tzinfo=timezone.utc)
        creds = _FakeCreds(expiry=expiry, scopes=None)
        fake_flow = MagicMock()
        fake_flow.credentials = creds
        _enable_libs(monkeypatch, flow=fake_flow, build_ret=MagicMock())
        _set_google_creds(monkeypatch)

        await GoogleCalendarService().handle_callback("c")

        saved = json.loads(gc.TOKEN_PATH.read_text())
        assert saved["expiry"] == expiry.isoformat()
        assert saved["scopes"] == gc.SCOPES  # falls back when creds.scopes is None

    async def test_error_reraised(self, monkeypatch):
        fake_flow = MagicMock()
        fake_flow.fetch_token.side_effect = RuntimeError("token-fail")
        _enable_libs(monkeypatch, flow=fake_flow)
        _set_google_creds(monkeypatch)
        with pytest.raises(RuntimeError, match="token-fail"):
            await GoogleCalendarService().handle_callback("c")


# ---------------------------------------------------------------------------
# is_connected
# ---------------------------------------------------------------------------


class TestIsConnected:
    def test_credentials_cached_returns_true(self):
        svc = GoogleCalendarService()
        svc._credentials = object()
        assert svc.is_connected() is True

    def test_no_token_file_returns_false(self):
        # autouse fixture points TOKEN_PATH at a non-existent temp file
        assert GoogleCalendarService().is_connected() is False

    def test_token_file_triggers_load(self, monkeypatch):
        gc.TOKEN_PATH.write_text("{}")
        svc = GoogleCalendarService()

        def _fake_load():
            svc._credentials = object()

        monkeypatch.setattr(svc, "_load_credentials", _fake_load)
        assert svc.is_connected() is True

    def test_load_raises_returns_false(self, monkeypatch):
        gc.TOKEN_PATH.write_text("{}")
        svc = GoogleCalendarService()
        monkeypatch.setattr(
            svc, "_load_credentials", MagicMock(side_effect=RuntimeError("nope"))
        )
        assert svc.is_connected() is False


# ---------------------------------------------------------------------------
# _load_credentials / _save_credentials
# ---------------------------------------------------------------------------


class TestLoadCredentials:
    def test_libs_unavailable_noop(self, monkeypatch):
        monkeypatch.setattr(gc, "GOOGLE_LIBS_AVAILABLE", False)
        svc = GoogleCalendarService()
        svc._load_credentials()
        assert svc._credentials is None

    def test_no_file_noop(self, monkeypatch):
        monkeypatch.setattr(gc, "GOOGLE_LIBS_AVAILABLE", True)
        svc = GoogleCalendarService()
        svc._load_credentials()
        assert svc._credentials is None

    def test_happy_builds_service(self, monkeypatch):
        gc.TOKEN_PATH.write_text(json.dumps({"token": "t", "refresh_token": "r"}))
        creds = _FakeCreds(expired=False)
        service = MagicMock()
        _enable_libs(
            monkeypatch,
            creds_factory=MagicMock(return_value=creds),
            build_ret=service,
        )
        svc = GoogleCalendarService()
        svc._load_credentials()
        assert svc._credentials is creds
        assert svc._service is service

    def test_refresh_branch(self, monkeypatch):
        # google-auth is installed in the venv, so the local
        # ``from google.auth.transport.requests import Request`` resolves for real;
        # ``_FakeCreds.refresh`` ignores the passed request object.
        gc.TOKEN_PATH.write_text(json.dumps({"token": "t", "refresh_token": "r"}))
        creds = _FakeCreds(expired=True, refresh_token="r")
        _enable_libs(
            monkeypatch,
            creds_factory=MagicMock(return_value=creds),
            build_ret=MagicMock(),
        )
        svc = GoogleCalendarService()
        svc._load_credentials()

        assert creds.refreshed is True
        # refreshed token was persisted back to disk
        assert json.loads(gc.TOKEN_PATH.read_text())["token"] == "refreshed-token"

    def test_load_error_resets_state(self, monkeypatch):
        gc.TOKEN_PATH.write_text("not-json{{{")
        monkeypatch.setattr(gc, "GOOGLE_LIBS_AVAILABLE", True)
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc._load_credentials()
        assert svc._credentials is None
        assert svc._service is None


class TestSaveCredentials:
    def test_no_credentials_noop(self):
        svc = GoogleCalendarService()
        svc._save_credentials()  # should not raise, nothing written
        assert not gc.TOKEN_PATH.exists()

    def test_happy_writes_file(self):
        svc = GoogleCalendarService()
        svc._credentials = _FakeCreds(token="saved", expiry=None, scopes=None)
        svc._save_credentials()
        saved = json.loads(gc.TOKEN_PATH.read_text())
        assert saved["token"] == "saved"
        assert saved["scopes"] == gc.SCOPES

    def test_write_error_swallowed(self, monkeypatch, tmp_path):
        # TOKEN_PATH whose parent dir does not exist -> write_text raises, caught.
        monkeypatch.setattr(gc, "TOKEN_PATH", tmp_path / "missing" / "tok.json")
        svc = GoogleCalendarService()
        svc._credentials = _FakeCreds()
        svc._save_credentials()  # must not raise
        assert not (tmp_path / "missing").exists()


# ---------------------------------------------------------------------------
# _ensure_service
# ---------------------------------------------------------------------------


class TestEnsureService:
    def test_service_present_ok(self):
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc._ensure_service()  # no raise

    def test_not_connected_raises(self):
        with pytest.raises(RuntimeError, match="not connected"):
            GoogleCalendarService()._ensure_service()


# ---------------------------------------------------------------------------
# list_calendars
# ---------------------------------------------------------------------------


class TestListCalendars:
    async def test_maps_items_with_defaults(self):
        svc = GoogleCalendarService()
        svc._service = _svc(
            calendars=[
                {"id": "c1", "summary": "Work", "primary": True},
                {"id": "c2"},  # missing optional fields -> defaults
            ]
        )
        result = await svc.list_calendars()
        assert [c["id"] for c in result] == ["c1", "c2"]
        assert result[0]["primary"] is True
        assert result[1]["summary"] == ""
        assert result[1]["primary"] is False

    async def test_error_reraised(self):
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc._service.calendarList.return_value.list.return_value.execute.side_effect = (
            RuntimeError("api down")
        )
        with pytest.raises(RuntimeError, match="api down"):
            await svc.list_calendars()


# ---------------------------------------------------------------------------
# get_events
# ---------------------------------------------------------------------------


class TestGetEvents:
    async def test_default_window_and_datetime(self):
        svc = GoogleCalendarService()
        svc._service = _svc(
            events=[
                {
                    "id": "e1",
                    "summary": "Meet",
                    "start": {"dateTime": "2030-01-01T10:00:00Z"},
                    "end": {"dateTime": "2030-01-01T11:00:00Z"},
                }
            ]
        )
        result = await svc.get_events()
        assert result[0]["id"] == "e1"
        assert result[0]["start"] == "2030-01-01T10:00:00Z"

    async def test_explicit_window_and_all_day_date(self):
        svc = GoogleCalendarService()
        svc._service = _svc(
            events=[{"id": "e2", "start": {"date": "2030-02-02"}, "end": {"date": "2030-02-03"}}]
        )
        result = await svc.get_events(
            calendar_id="cal", time_min="2030-01-01T00:00:00Z", time_max="2030-01-08T00:00:00Z"
        )
        assert result[0]["start"] == "2030-02-02"  # falls back to date
        assert result[0]["summary"] == ""

    async def test_error_reraised(self):
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc._service.events.return_value.list.return_value.execute.side_effect = (
            RuntimeError("boom")
        )
        with pytest.raises(RuntimeError, match="boom"):
            await svc.get_events()


# ---------------------------------------------------------------------------
# create_event
# ---------------------------------------------------------------------------


class TestCreateEvent:
    async def test_missing_summary_raises(self):
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        with pytest.raises(ValueError, match="summary is required"):
            await svc.create_event(summary="", start="s", end="e")

    async def test_missing_times_raises(self):
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        with pytest.raises(ValueError, match="start and end"):
            await svc.create_event(summary="Title", start="", end="")

    async def test_happy_returns_event(self):
        svc = GoogleCalendarService()
        svc._service = _svc(
            created={
                "id": "evt1",
                "summary": "Title",
                "start": {"dateTime": "2030-01-01T10:00:00Z"},
                "end": {"dateTime": "2030-01-01T11:00:00Z"},
                "htmlLink": "http://link",
                "status": "confirmed",
            }
        )
        result = await svc.create_event(
            summary="Title", start="2030-01-01T10:00:00Z", end="2030-01-01T11:00:00Z"
        )
        assert result["id"] == "evt1"
        assert result["html_link"] == "http://link"

    async def test_error_reraised(self):
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc._service.events.return_value.insert.return_value.execute.side_effect = (
            RuntimeError("insert-fail")
        )
        with pytest.raises(RuntimeError, match="insert-fail"):
            await svc.create_event(summary="T", start="s", end="e")


# ---------------------------------------------------------------------------
# sync_prompts_from_calendar
# ---------------------------------------------------------------------------


def _patched_store(monkeypatch, **overrides):
    """Patch PromptStore constructor to return a MagicMock with async methods."""
    store = MagicMock()
    store.initialize = AsyncMock()
    store.close = AsyncMock()
    store.create_prompt = AsyncMock(return_value=overrides.get("prompt_id", "pid-1"))
    store.list_prompts = AsyncMock(return_value=overrides.get("list_prompts", {"prompts": []}))
    store.update_prompt = AsyncMock()
    monkeypatch.setattr(
        "app.services.prompt_store.PromptStore", MagicMock(return_value=store)
    )
    return store


class TestSyncFromCalendar:
    async def test_creates_prompt_for_tagged_event(self, monkeypatch):
        store = _patched_store(monkeypatch)
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc.get_events = AsyncMock(
            return_value=[
                {"id": "e1", "summary": "[PROMPT] do thing", "start": "2030-01-01T10:00:00Z"},
                {"id": "e2", "summary": "no tag here", "start": ""},  # skipped
            ]
        )
        result = await svc.sync_prompts_from_calendar()
        assert result["synced"] == 1
        assert result["prompt_ids"] == ["pid-1"]
        assert "e1" in svc._synced_event_ids
        store.create_prompt.assert_awaited_once()
        assert store.create_prompt.await_args.kwargs["content"] == "do thing"
        store.close.assert_awaited_once()

    async def test_skips_already_synced(self, monkeypatch):
        _patched_store(monkeypatch)
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc._synced_event_ids.add("e1")
        svc.get_events = AsyncMock(
            return_value=[{"id": "e1", "summary": "[PROMPT] x", "start": ""}]
        )
        result = await svc.sync_prompts_from_calendar()
        assert result["synced"] == 0

    async def test_empty_content_uses_description(self, monkeypatch):
        store = _patched_store(monkeypatch)
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc.get_events = AsyncMock(
            return_value=[
                {
                    "id": "e3",
                    "summary": "[PROMPT]",  # nothing left after strip
                    "description": "from description",
                    "start": "not-a-date",  # unparseable -> scheduled_at None
                }
            ]
        )
        result = await svc.sync_prompts_from_calendar()
        assert result["synced"] == 1
        kwargs = store.create_prompt.await_args.kwargs
        assert kwargs["content"] == "from description"
        assert kwargs["scheduled_at"] is None

    async def test_error_reraised_and_store_closed(self, monkeypatch):
        store = _patched_store(monkeypatch)
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc.get_events = AsyncMock(side_effect=RuntimeError("events-fail"))
        with pytest.raises(RuntimeError, match="events-fail"):
            await svc.sync_prompts_from_calendar()
        store.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# sync_results_to_calendar
# ---------------------------------------------------------------------------


class TestSyncToCalendar:
    async def test_creates_event_and_marks_synced(self, monkeypatch):
        store = _patched_store(
            monkeypatch,
            list_prompts={
                "prompts": [
                    {
                        "prompt_id": "p1",
                        "content": "hello",
                        "output": "result text",
                        "completed_at": "2030-01-01T12:00:00Z",
                        "metadata": {},
                    }
                ]
            },
        )
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc.create_event = AsyncMock(return_value={"id": "evt-9"})
        result = await svc.sync_results_to_calendar()
        assert result["synced"] == 1
        assert result["event_ids"] == ["evt-9"]
        svc.create_event.assert_awaited_once()
        store.update_prompt.assert_awaited_once()
        assert store.update_prompt.await_args.kwargs["metadata_json"]["synced_to_calendar"] is True

    async def test_skips_no_output_already_synced_and_no_completed_at(self, monkeypatch):
        _patched_store(
            monkeypatch,
            list_prompts={
                "prompts": [
                    {"prompt_id": "a", "output": ""},  # no output
                    {"prompt_id": "b", "output": "x", "metadata": {"synced_to_calendar": True}},
                    {"prompt_id": "c", "output": "x", "metadata": {}, "completed_at": ""},
                ]
            },
        )
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc.create_event = AsyncMock()
        result = await svc.sync_results_to_calendar()
        assert result["synced"] == 0
        svc.create_event.assert_not_awaited()

    async def test_bad_completed_at_falls_back_to_now(self, monkeypatch):
        _patched_store(
            monkeypatch,
            list_prompts={
                "prompts": [
                    {
                        "prompt_id": "p2",
                        "content": "c",
                        "output": "o",
                        "completed_at": "garbage",
                        "metadata": {},
                    }
                ]
            },
        )
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        svc.create_event = AsyncMock(return_value={"id": "e"})
        result = await svc.sync_results_to_calendar()
        assert result["synced"] == 1

    async def test_error_reraised_and_store_closed(self, monkeypatch):
        store = _patched_store(monkeypatch)
        store.list_prompts = AsyncMock(side_effect=RuntimeError("list-fail"))
        svc = GoogleCalendarService()
        svc._service = MagicMock()
        with pytest.raises(RuntimeError, match="list-fail"):
            await svc.sync_results_to_calendar()
        store.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# disconnect / get_status / singleton
# ---------------------------------------------------------------------------


class TestDisconnect:
    async def test_removes_token_and_clears_state(self):
        gc.TOKEN_PATH.write_text("{}")
        svc = GoogleCalendarService()
        svc._credentials = object()
        svc._service = MagicMock()
        svc._synced_event_ids.add("x")
        svc._last_sync = datetime.now(timezone.utc)

        result = await svc.disconnect()
        assert result["success"] is True
        assert not gc.TOKEN_PATH.exists()
        assert svc._credentials is None
        assert svc._service is None
        assert svc._synced_event_ids == set()
        assert svc._last_sync is None

    async def test_no_token_file_still_succeeds(self):
        result = await GoogleCalendarService().disconnect()
        assert result["success"] is True

    async def test_unlink_error_reraised(self, monkeypatch):
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        fake_path.unlink.side_effect = OSError("locked")
        monkeypatch.setattr(gc, "TOKEN_PATH", fake_path)
        with pytest.raises(OSError, match="locked"):
            await GoogleCalendarService().disconnect()


class TestStatus:
    def test_shape_disconnected(self):
        status = GoogleCalendarService().get_status()
        assert status["connected"] is False
        assert status["google_libs_available"] == gc.GOOGLE_LIBS_AVAILABLE
        assert status["token_exists"] is False
        assert status["last_sync"] is None
        assert status["synced_events_count"] == 0

    def test_last_sync_serialised(self):
        svc = GoogleCalendarService()
        svc._credentials = object()  # connected
        svc._last_sync = datetime(2030, 5, 5, tzinfo=timezone.utc)
        status = svc.get_status()
        assert status["connected"] is True
        assert status["last_sync"] == datetime(2030, 5, 5, tzinfo=timezone.utc).isoformat()


class TestSingleton:
    def test_get_google_calendar_cached(self):
        a = get_google_calendar()
        b = get_google_calendar()
        assert a is b
        assert isinstance(a, GoogleCalendarService)


class TestImportFallback:
    """Cover the optional-dependency import guard at module load (lines 24-28).

    The google client libs ARE installed in this environment (so ``GOOGLE_LIBS_AVAILABLE``
    is normally ``True`` and the ``except ImportError`` block never runs). We reload the
    module with those three submodules forced to ``None`` in ``sys.modules`` — which makes
    ``from ... import ...`` raise ``ImportError`` — then restore the real modules and reload
    back so no other test is affected.
    """

    def test_module_falls_back_when_google_libs_absent(self):
        import importlib
        import sys

        blocked = [
            "google.oauth2.credentials",
            "google_auth_oauthlib.flow",
            "googleapiclient.discovery",
        ]
        saved = {name: sys.modules.get(name) for name in blocked}
        try:
            for name in blocked:
                sys.modules[name] = None  # -> ImportError on `from <name> import ...`
            importlib.reload(gc)
            assert gc.GOOGLE_LIBS_AVAILABLE is False
            assert gc.Credentials is None
            assert gc.Flow is None
            assert gc.build is None
        finally:
            for name, mod in saved.items():
                if mod is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = mod
            importlib.reload(gc)  # restore real module state (libs available again)
        assert gc.GOOGLE_LIBS_AVAILABLE is True
