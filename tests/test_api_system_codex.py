"""
Tests for the macOS/OSASCRIPT system API router (app/api/v1/system.py).

The 28 endpoints all share the same shape: guard on ``settings.osascript_enabled``
(``check_osascript_enabled`` → 503), call a **synchronous** method on the module-level
singleton ``osascript_service``, then ``await audit_logger.log_operation(...)``. So we:

- monkeypatch the name bound in the router namespace (``app.api.v1.system.osascript_service``)
  with a plain ``MagicMock`` — every method is sync, none is ``await``ed. The real singleton
  (which shells out to ``osascript`` on macOS) is never touched: no subprocess, no macOS.
- use ``audit_logger`` **real**: ``log_operation`` reads ``getattr(request.app.state,
  'event_store', None)``; the bare ``FastAPI()`` here has no ``event_store`` → it degrades
  without any disk/DB/network.
- authenticate with a **real** key (``api_key_manager.generate_key(permissions={"all"})``),
  same as ``test_api_frangels_codex.py`` — it passes ``verify_api_key`` + write-permission +
  rate-limit.

High-risk write endpoints wrap an ``OSAScriptSecurityContext`` (pure CM reading ``settings``);
the 403 branch is forced by adding the op to ``settings.osascript_disabled_operations``.
No infra, no network, no ``.env``.
"""

import contextlib
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import system
from app.core.security import api_key_manager
from app.services.osascript import OSAScriptError

# Dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-system", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}

# Inputs the real sanitizer accepts (see AppleScriptSanitizer.validate_url/validate_path).
VALID_URL = "https://example.com"
VALID_PATH = "/Users/test/file.txt"
BAD_PATH = "/etc/passwd"  # not under an allowed prefix → validate_path raises ValueError → 400


def build_app() -> FastAPI:
    """Build a FastAPI app with only the system router mounted."""
    app = FastAPI()
    app.include_router(system.router, prefix="/api/v1")
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def svc(monkeypatch):
    """Replace the module-level ``osascript_service`` with a sync MagicMock."""
    fake = MagicMock()
    monkeypatch.setattr(system, "osascript_service", fake)
    return fake


@contextlib.asynccontextmanager
async def _client():
    async with client_for(build_app()) as c:
        yield c


# =============================================================================
# SISTEMA — /info, /apps
# =============================================================================


async def test_info_happy(svc):
    svc.get_system_info.return_value = {"os": "macOS", "version": "15.0"}
    svc.get_frontmost_app.return_value = "Finder"
    svc.is_dark_mode.return_value = True
    svc.get_volume.return_value = 42
    async with _client() as c:
        r = await c.get("/api/v1/system/info", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["os"] == "macOS"
    assert body["frontmost_app"] == "Finder"
    assert body["dark_mode"] is True
    assert body["volume"] == 42


async def test_info_osascript_error_500(svc):
    svc.get_system_info.side_effect = OSAScriptError("boom")
    async with _client() as c:
        r = await c.get("/api/v1/system/info", headers=AUTH)
    assert r.status_code == 500
    assert r.json()["detail"] == "boom"


async def test_apps_happy(svc):
    svc.get_running_apps.return_value = ["Safari", "Mail"]
    svc.get_frontmost_app.return_value = "Safari"
    async with _client() as c:
        r = await c.get("/api/v1/system/apps", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["apps"] == ["Safari", "Mail"]
    assert body["count"] == 2
    assert body["frontmost"] == "Safari"


async def test_apps_error_500(svc):
    svc.get_running_apps.side_effect = OSAScriptError("fail")
    async with _client() as c:
        r = await c.get("/api/v1/system/apps", headers=AUTH)
    assert r.status_code == 500


# =============================================================================
# /notify, /speak  (validators: subtitle present/absent, sound + voice fallbacks)
# =============================================================================


async def test_notify_success_subtitle_and_bad_sound(svc):
    """subtitle truthy branch + invalid sound → 'default' fallback."""
    svc.send_notification.return_value = True
    payload = {"title": "Hi", "message": "there", "subtitle": "sub", "sound": "NotASound"}
    async with _client() as c:
        r = await c.post("/api/v1/system/notify", headers=AUTH, json=payload)
    assert r.status_code == 200
    assert r.json() == {"status": "sent", "title": "Hi"}
    # validator coerced the unknown sound back to "default"
    assert svc.send_notification.call_args.kwargs["sound"] == "default"


async def test_notify_success_no_subtitle_valid_sound(svc):
    """subtitle falsy branch (explicit "" so the validator still runs) + a
    whitelisted sound kept as-is."""
    svc.send_notification.return_value = True
    payload = {"title": "Hi", "message": "there", "subtitle": "", "sound": "Glass"}
    async with _client() as c:
        r = await c.post("/api/v1/system/notify", headers=AUTH, json=payload)
    assert r.status_code == 200
    assert svc.send_notification.call_args.kwargs["sound"] == "Glass"


async def test_notify_failure_500(svc):
    svc.send_notification.return_value = False
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/notify", headers=AUTH,
            json={"title": "Hi", "message": "there"},
        )
    assert r.status_code == 500


async def test_notify_missing_message_422(svc):
    async with _client() as c:
        r = await c.post("/api/v1/system/notify", headers=AUTH, json={"title": "Hi"})
    assert r.status_code == 422


async def test_speak_success_bad_voice(svc):
    """invalid voice → 'Samantha' fallback."""
    svc.say_text.return_value = True
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/speak", headers=AUTH,
            json={"text": "hola", "voice": "NopeVoice"},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "speaking"
    assert svc.say_text.call_args.kwargs["voice"] == "Samantha"


async def test_speak_success_valid_voice(svc):
    svc.say_text.return_value = True
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/speak", headers=AUTH,
            json={"text": "hola", "voice": "Alex"},
        )
    assert r.status_code == 200
    assert svc.say_text.call_args.kwargs["voice"] == "Alex"


async def test_speak_failure_500(svc):
    svc.say_text.return_value = False
    async with _client() as c:
        r = await c.post("/api/v1/system/speak", headers=AUTH, json={"text": "hola"})
    assert r.status_code == 500


# =============================================================================
# /volume  (GET + POST high-risk: happy, 500, 403)
# =============================================================================


async def test_get_volume_happy(svc):
    svc.get_volume.return_value = 55
    async with _client() as c:
        r = await c.get("/api/v1/system/volume", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"volume": 55}


async def test_get_volume_error_500(svc):
    svc.get_volume.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/volume", headers=AUTH)
    assert r.status_code == 500


async def test_set_volume_happy_and_clamp(svc):
    """level > 100 clamped to 100 by the validator."""
    svc.set_volume.return_value = True
    async with _client() as c:
        r = await c.post("/api/v1/system/volume", headers=AUTH, json={"level": 250})
    assert r.status_code == 200
    assert r.json() == {"status": "set", "volume": 100}
    svc.set_volume.assert_called_once_with(100)


async def test_set_volume_failure_500(svc):
    svc.set_volume.return_value = False
    async with _client() as c:
        r = await c.post("/api/v1/system/volume", headers=AUTH, json={"level": 30})
    assert r.status_code == 500


async def test_set_volume_disabled_403(svc, monkeypatch):
    monkeypatch.setattr(
        system.settings, "osascript_disabled_operations", ["set_volume"], raising=False
    )
    async with _client() as c:
        r = await c.post("/api/v1/system/volume", headers=AUTH, json={"level": 30})
    assert r.status_code == 403


# =============================================================================
# /dark-mode  (GET + toggle high-risk)
# =============================================================================


async def test_toggle_dark_mode_happy(svc):
    svc.toggle_dark_mode.return_value = True
    svc.is_dark_mode.return_value = False
    async with _client() as c:
        r = await c.post("/api/v1/system/dark-mode/toggle", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"status": "toggled", "dark_mode": False}


async def test_toggle_dark_mode_failure_500(svc):
    svc.toggle_dark_mode.return_value = False
    async with _client() as c:
        r = await c.post("/api/v1/system/dark-mode/toggle", headers=AUTH)
    assert r.status_code == 500


async def test_toggle_dark_mode_disabled_403(svc, monkeypatch):
    monkeypatch.setattr(
        system.settings, "osascript_disabled_operations", ["toggle_dark_mode"],
        raising=False,
    )
    async with _client() as c:
        r = await c.post("/api/v1/system/dark-mode/toggle", headers=AUTH)
    assert r.status_code == 403


async def test_get_dark_mode_happy(svc):
    svc.is_dark_mode.return_value = True
    async with _client() as c:
        r = await c.get("/api/v1/system/dark-mode", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["dark_mode"] is True


async def test_get_dark_mode_error_500(svc):
    svc.is_dark_mode.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/dark-mode", headers=AUTH)
    assert r.status_code == 500


# =============================================================================
# CALENDAR
# =============================================================================


async def test_calendar_lists_happy(svc):
    svc.get_calendars.return_value = ["Home", "Work"]
    async with _client() as c:
        r = await c.get("/api/v1/system/calendar/lists", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"calendars": ["Home", "Work"], "count": 2}


async def test_calendar_lists_error_500(svc):
    svc.get_calendars.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/calendar/lists", headers=AUTH)
    assert r.status_code == 500


async def test_calendar_today_with_calendar_param(svc):
    """`calendar` query provided → sanitize branch."""
    svc.get_today_events.return_value = [{"title": "Standup"}]
    async with _client() as c:
        r = await c.get("/api/v1/system/calendar/today?calendar=Work", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert "date" in body


async def test_calendar_today_no_param(svc):
    svc.get_today_events.return_value = []
    async with _client() as c:
        r = await c.get("/api/v1/system/calendar/today", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["count"] == 0


async def test_calendar_today_error_500(svc):
    svc.get_today_events.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/calendar/today", headers=AUTH)
    assert r.status_code == 500


async def test_create_calendar_event_with_optionals(svc):
    """location + notes truthy branches."""
    svc.create_calendar_event.return_value = True
    payload = {
        "title": "Meet",
        "start_date": "2026-07-14T10:00:00",
        "end_date": "2026-07-14T11:00:00",
        "location": "Office",
        "notes": "bring laptop",
    }
    async with _client() as c:
        r = await c.post("/api/v1/system/calendar/events", headers=AUTH, json=payload)
    assert r.status_code == 200
    assert r.json() == {"status": "created", "title": "Meet"}


async def test_create_calendar_event_no_optionals_failure_500(svc):
    """location + notes falsy branches (explicit "" so the validators still run)
    + failure path."""
    svc.create_calendar_event.return_value = False
    payload = {
        "title": "Meet",
        "start_date": "2026-07-14T10:00:00",
        "end_date": "2026-07-14T11:00:00",
        "location": "",
        "notes": "",
    }
    async with _client() as c:
        r = await c.post("/api/v1/system/calendar/events", headers=AUTH, json=payload)
    assert r.status_code == 500


# =============================================================================
# REMINDERS
# =============================================================================


async def test_reminder_lists_happy(svc):
    svc.get_reminder_lists.return_value = ["Reminders"]
    async with _client() as c:
        r = await c.get("/api/v1/system/reminders/lists", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["count"] == 1


async def test_reminder_lists_error_500(svc):
    svc.get_reminder_lists.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/reminders/lists", headers=AUTH)
    assert r.status_code == 500


async def test_get_reminders_with_list_name(svc):
    svc.get_reminders.return_value = [{"name": "Buy milk"}]
    async with _client() as c:
        r = await c.get(
            "/api/v1/system/reminders?list_name=Work&include_completed=true",
            headers=AUTH,
        )
    assert r.status_code == 200
    assert r.json()["count"] == 1
    svc.get_reminders.assert_called_once()
    assert svc.get_reminders.call_args.args[1] is True  # include_completed


async def test_get_reminders_no_list(svc):
    svc.get_reminders.return_value = []
    async with _client() as c:
        r = await c.get("/api/v1/system/reminders", headers=AUTH)
    assert r.status_code == 200


async def test_get_reminders_error_500(svc):
    svc.get_reminders.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/reminders", headers=AUTH)
    assert r.status_code == 500


async def test_create_reminder_with_notes(svc):
    svc.create_reminder.return_value = True
    payload = {"name": "Task", "notes": "detail"}
    async with _client() as c:
        r = await c.post("/api/v1/system/reminders", headers=AUTH, json=payload)
    assert r.status_code == 200
    assert r.json() == {"status": "created", "name": "Task"}


async def test_create_reminder_no_notes_failure_500(svc):
    """notes falsy branch (explicit "" so the validator still runs) + failure path."""
    svc.create_reminder.return_value = False
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/reminders", headers=AUTH, json={"name": "T", "notes": ""}
        )
    assert r.status_code == 500


async def test_complete_reminder_happy(svc):
    svc.complete_reminder.return_value = True
    async with _client() as c:
        r = await c.post("/api/v1/system/reminders/Task/complete", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"status": "completed", "name": "Task"}


async def test_complete_reminder_failure_500(svc):
    svc.complete_reminder.return_value = False
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/reminders/Task/complete?list_name=Work", headers=AUTH
        )
    assert r.status_code == 500


# =============================================================================
# NOTES
# =============================================================================


async def test_note_folders_happy(svc):
    svc.get_note_folders.return_value = ["Notes"]
    async with _client() as c:
        r = await c.get("/api/v1/system/notes/folders", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["count"] == 1


async def test_note_folders_error_500(svc):
    svc.get_note_folders.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/notes/folders", headers=AUTH)
    assert r.status_code == 500


async def test_get_notes_with_folder(svc):
    svc.get_notes.return_value = [{"title": "n1"}]
    async with _client() as c:
        r = await c.get("/api/v1/system/notes?folder=Work&limit=5", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["count"] == 1


async def test_get_notes_no_folder(svc):
    svc.get_notes.return_value = []
    async with _client() as c:
        r = await c.get("/api/v1/system/notes", headers=AUTH)
    assert r.status_code == 200


async def test_get_notes_error_500(svc):
    svc.get_notes.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/notes", headers=AUTH)
    assert r.status_code == 500


async def test_create_note_happy(svc):
    svc.create_note.return_value = True
    payload = {"title": "T", "body": "B"}
    async with _client() as c:
        r = await c.post("/api/v1/system/notes", headers=AUTH, json=payload)
    assert r.status_code == 200
    assert r.json() == {"status": "created", "title": "T"}


async def test_create_note_failure_500(svc):
    svc.create_note.return_value = False
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/notes", headers=AUTH, json={"title": "T", "body": "B"}
        )
    assert r.status_code == 500


# =============================================================================
# SAFARI
# =============================================================================


async def test_safari_tabs_happy(svc):
    svc.get_safari_tabs.return_value = [{"title": "t"}]
    async with _client() as c:
        r = await c.get("/api/v1/system/safari/tabs", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["count"] == 1


async def test_safari_tabs_error_500(svc):
    svc.get_safari_tabs.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/safari/tabs", headers=AUTH)
    assert r.status_code == 500


async def test_safari_current_happy(svc):
    svc.get_current_safari_url.return_value = "https://a.b"
    async with _client() as c:
        r = await c.get("/api/v1/system/safari/current", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"url": "https://a.b"}


async def test_safari_current_error_500(svc):
    svc.get_current_safari_url.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/safari/current", headers=AUTH)
    assert r.status_code == 500


async def test_safari_open_happy(svc):
    svc.open_url_in_safari.return_value = True
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/safari/open", headers=AUTH,
            json={"url": VALID_URL, "new_tab": True},
        )
    assert r.status_code == 200
    assert r.json() == {"status": "opened", "url": VALID_URL}


async def test_safari_open_failure_500(svc):
    svc.open_url_in_safari.return_value = False
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/safari/open", headers=AUTH, json={"url": VALID_URL}
        )
    assert r.status_code == 500


async def test_safari_open_disabled_403(svc, monkeypatch):
    monkeypatch.setattr(
        system.settings, "osascript_disabled_operations", ["open_url_in_safari"],
        raising=False,
    )
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/safari/open", headers=AUTH, json={"url": VALID_URL}
        )
    assert r.status_code == 403


async def test_safari_open_invalid_url_422(svc):
    """validate_url rejects non-http scheme at request-validation time."""
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/safari/open", headers=AUTH, json={"url": "ftp://x"}
        )
    assert r.status_code == 422


# =============================================================================
# CONTACTS
# =============================================================================


async def test_contacts_search_happy(svc):
    svc.search_contacts.return_value = [{"name": "Ada"}]
    async with _client() as c:
        r = await c.get("/api/v1/system/contacts/search?q=Ada", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "Ada"
    assert body["count"] == 1


async def test_contacts_search_error_500(svc):
    svc.search_contacts.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/contacts/search?q=Ada", headers=AUTH)
    assert r.status_code == 500


async def test_contacts_search_query_too_short_422(svc):
    async with _client() as c:
        r = await c.get("/api/v1/system/contacts/search?q=A", headers=AUTH)
    assert r.status_code == 422


# =============================================================================
# FINDER
# =============================================================================


async def test_finder_selection_happy(svc):
    svc.get_selected_files.return_value = ["/Users/a/f.txt"]
    async with _client() as c:
        r = await c.get("/api/v1/system/finder/selection", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["count"] == 1


async def test_finder_selection_error_500(svc):
    svc.get_selected_files.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/finder/selection", headers=AUTH)
    assert r.status_code == 500


async def test_finder_reveal_happy(svc):
    svc.reveal_in_finder.return_value = True
    async with _client() as c:
        r = await c.post(
            f"/api/v1/system/finder/reveal?path={VALID_PATH}", headers=AUTH
        )
    assert r.status_code == 200
    assert r.json() == {"status": "revealed", "path": VALID_PATH}


async def test_finder_reveal_failure_500(svc):
    svc.reveal_in_finder.return_value = False
    async with _client() as c:
        r = await c.post(
            f"/api/v1/system/finder/reveal?path={VALID_PATH}", headers=AUTH
        )
    assert r.status_code == 500


async def test_finder_reveal_invalid_path_400(svc):
    """validate_path raises ValueError for a path outside allowed prefixes → 400."""
    async with _client() as c:
        r = await c.post(
            f"/api/v1/system/finder/reveal?path={BAD_PATH}", headers=AUTH
        )
    assert r.status_code == 400


async def test_finder_reveal_disabled_403(svc, monkeypatch):
    monkeypatch.setattr(
        system.settings, "osascript_disabled_operations", ["reveal_in_finder"],
        raising=False,
    )
    async with _client() as c:
        r = await c.post(
            f"/api/v1/system/finder/reveal?path={VALID_PATH}", headers=AUTH
        )
    assert r.status_code == 403


# =============================================================================
# CLIPBOARD
# =============================================================================


async def test_get_clipboard_happy(svc):
    svc.get_clipboard.return_value = "copied text"
    async with _client() as c:
        r = await c.get("/api/v1/system/clipboard", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"content": "copied text"}


async def test_get_clipboard_error_500(svc):
    svc.get_clipboard.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/clipboard", headers=AUTH)
    assert r.status_code == 500


async def test_set_clipboard_happy(svc):
    svc.set_clipboard.return_value = True
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/clipboard", headers=AUTH, json={"text": "hello"}
        )
    assert r.status_code == 200
    assert r.json() == {"status": "set"}


async def test_set_clipboard_failure_500(svc):
    svc.set_clipboard.return_value = False
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/clipboard", headers=AUTH, json={"text": "hello"}
        )
    assert r.status_code == 500


async def test_set_clipboard_disabled_403(svc, monkeypatch):
    monkeypatch.setattr(
        system.settings, "osascript_disabled_operations", ["set_clipboard"],
        raising=False,
    )
    async with _client() as c:
        r = await c.post(
            "/api/v1/system/clipboard", headers=AUTH, json={"text": "hello"}
        )
    assert r.status_code == 403


# =============================================================================
# MUSIC
# =============================================================================


async def test_music_current_playing(svc):
    svc.get_current_track.return_value = {"name": "Song", "artist": "X"}
    async with _client() as c:
        r = await c.get("/api/v1/system/music/current", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["playing"] is True
    assert body["track"]["name"] == "Song"


async def test_music_current_not_playing(svc):
    svc.get_current_track.return_value = None
    async with _client() as c:
        r = await c.get("/api/v1/system/music/current", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"playing": False, "track": None}


async def test_music_current_error_500(svc):
    svc.get_current_track.side_effect = OSAScriptError("x")
    async with _client() as c:
        r = await c.get("/api/v1/system/music/current", headers=AUTH)
    assert r.status_code == 500


async def test_music_playpause_happy(svc):
    svc.music_play_pause.return_value = True
    async with _client() as c:
        r = await c.post("/api/v1/system/music/playpause", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"status": "toggled"}


async def test_music_playpause_failure_500(svc):
    svc.music_play_pause.return_value = False
    async with _client() as c:
        r = await c.post("/api/v1/system/music/playpause", headers=AUTH)
    assert r.status_code == 500


# =============================================================================
# CROSS-CUTTING — 503 (module disabled) + auth (401)
# =============================================================================

_DISABLED_CASES = [
    ("get", "/api/v1/system/info", None),
    ("post", "/api/v1/system/notify", {"title": "a", "message": "b"}),
    ("post", "/api/v1/system/volume", {"level": 10}),
]


@pytest.mark.parametrize("method,path,body", _DISABLED_CASES)
async def test_returns_503_when_osascript_disabled(svc, monkeypatch, method, path, body):
    monkeypatch.setattr(system.settings, "osascript_enabled", False)
    async with _client() as c:
        kwargs = {"headers": AUTH}
        if body is not None:
            kwargs["json"] = body
        r = await getattr(c, method)(path, **kwargs)
    assert r.status_code == 503
    assert r.json()["detail"] == "OSASCRIPT module is disabled"


_AUTH_CASES = [
    ("get", "/api/v1/system/info"),
    ("get", "/api/v1/system/apps"),
    ("post", "/api/v1/system/notify"),
    ("post", "/api/v1/system/volume"),
    ("get", "/api/v1/system/clipboard"),
    ("post", "/api/v1/system/music/playpause"),
]


@pytest.mark.parametrize("method,path", _AUTH_CASES)
async def test_requires_auth(svc, monkeypatch, method, path):
    """With auth enforced, a missing X-API-Key → 401 during dependency resolution
    (``verify_api_key`` raises before ``check_rate_limit`` ever runs)."""
    monkeypatch.setattr(
        system.settings, "osascript_require_auth", True, raising=False
    )
    async with _client() as c:
        r = await getattr(c, method)(path)
    assert r.status_code == 401
