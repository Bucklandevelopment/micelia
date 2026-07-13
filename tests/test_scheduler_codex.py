"""
Tests for PromptScheduler: time-based prompt triggering + calendar sync.

Store, event bus and Google Calendar service are all mocked/patched; the loop
sleep is monkeypatched. No infra.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import scheduler as sched
from app.services.scheduler import PromptScheduler, get_scheduler


@pytest.fixture
def store():
    return AsyncMock()


# --------------------------------------------------------------------------
# _process_scheduled
# --------------------------------------------------------------------------

async def test_process_scheduled_no_store_returns():
    s = PromptScheduler()  # no store
    await s._process_scheduled()  # no raise


async def test_process_scheduled_empty_returns(store):
    store.get_scheduled_prompts.return_value = []
    s = PromptScheduler(store)
    await s._process_scheduled()
    store.update_prompt.assert_not_called()
    assert s._scheduled_moved == 0


async def test_process_scheduled_moves_and_publishes(store):
    bus = AsyncMock()
    store.get_scheduled_prompts.return_value = [
        {"prompt_id": "p1", "category": "work", "scheduled_at": "2026-01-01T00:00:00"},
        {"prompt_id": "p2", "category": "note"},
    ]
    s = PromptScheduler(store, event_bus=bus)
    await s._process_scheduled()
    assert store.update_prompt.await_count == 2
    assert s._scheduled_moved == 2
    assert bus.publish.await_count == 2
    assert store.update_prompt.await_args.kwargs["status"] == "queued"


async def test_process_scheduled_event_error_swallowed(store):
    bus = AsyncMock()
    bus.publish.side_effect = RuntimeError("bus down")
    store.get_scheduled_prompts.return_value = [{"prompt_id": "p1"}]
    s = PromptScheduler(store, event_bus=bus)
    await s._process_scheduled()  # no raise
    assert s._scheduled_moved == 1


async def test_process_scheduled_store_error_swallowed(store):
    store.get_scheduled_prompts.side_effect = RuntimeError("db down")
    s = PromptScheduler(store)
    await s._process_scheduled()  # outer try swallows it
    assert s._scheduled_moved == 0


# --------------------------------------------------------------------------
# _sync_calendar
# --------------------------------------------------------------------------

async def test_sync_calendar_disabled_returns(monkeypatch):
    monkeypatch.setattr(sched.settings, "google_calendar_enabled", False, raising=False)
    s = PromptScheduler()
    await s._sync_calendar()
    assert s.synced_count == 0


async def test_sync_calendar_connected_syncs(monkeypatch):
    monkeypatch.setattr(sched.settings, "google_calendar_enabled", True, raising=False)
    import app.services.google_calendar as gc

    gcal = MagicMock()
    gcal.is_connected.return_value = True
    gcal.sync_prompts_from_calendar = AsyncMock(return_value={"synced": 3})
    monkeypatch.setattr(gc, "get_google_calendar", lambda: gcal)

    s = PromptScheduler()
    await s._sync_calendar()
    assert s.synced_count == 3


async def test_sync_calendar_not_connected(monkeypatch):
    monkeypatch.setattr(sched.settings, "google_calendar_enabled", True, raising=False)
    import app.services.google_calendar as gc

    gcal = MagicMock()
    gcal.is_connected.return_value = False
    monkeypatch.setattr(gc, "get_google_calendar", lambda: gcal)

    s = PromptScheduler()
    await s._sync_calendar()
    assert s.synced_count == 0


async def test_sync_calendar_error_swallowed(monkeypatch):
    monkeypatch.setattr(sched.settings, "google_calendar_enabled", True, raising=False)
    import app.services.google_calendar as gc

    gcal = MagicMock()
    gcal.is_connected.return_value = True
    gcal.sync_prompts_from_calendar = AsyncMock(side_effect=RuntimeError("api down"))
    monkeypatch.setattr(gc, "get_google_calendar", lambda: gcal)

    s = PromptScheduler()
    await s._sync_calendar()  # no raise
    assert s.synced_count == 0


async def test_sync_calendar_import_error_swallowed(monkeypatch):
    # get_google_calendar lanza ImportError (p.ej. libs de Google ausentes) ->
    # la rama `except ImportError` (línea 137) hace log.debug y no propaga.
    monkeypatch.setattr(sched.settings, "google_calendar_enabled", True, raising=False)
    import app.services.google_calendar as gc

    def _boom():
        raise ImportError("google calendar service not installed")

    monkeypatch.setattr(gc, "get_google_calendar", _boom)

    s = PromptScheduler()
    await s._sync_calendar()  # no raise
    assert s.synced_count == 0


# --------------------------------------------------------------------------
# get_status + singleton
# --------------------------------------------------------------------------

def test_get_status_shape():
    s = PromptScheduler()
    status = s.get_status()
    assert status["running"] is False
    assert status["last_scan"] is None
    assert "interval_seconds" in status
    assert "total_scheduled_moved" in status
    assert "total_calendar_synced" in status


def test_get_scheduler_singleton(monkeypatch):
    monkeypatch.setattr(sched, "_scheduler", None)
    a = get_scheduler()
    b = get_scheduler()
    assert a is b


# --------------------------------------------------------------------------
# lifecycle + loop
# --------------------------------------------------------------------------

async def test_start_stop(store):
    s = PromptScheduler(store)
    store.get_scheduled_prompts.return_value = []
    await s.start()
    assert s.running is True
    first = s._task
    await s.start()  # double-start no-op
    assert s._task is first
    await s.stop()
    assert s.running is False
    assert s._task.done()


async def test_run_loop_one_cycle_then_cancel(store, monkeypatch):
    monkeypatch.setattr(sched.settings, "google_calendar_enabled", False, raising=False)
    store.get_scheduled_prompts.return_value = []
    s = PromptScheduler(store)
    s.running = True

    async def fake_sleep(_):
        raise asyncio.CancelledError

    monkeypatch.setattr(sched.asyncio, "sleep", fake_sleep)
    await s._run_loop()
    assert s.last_scan is not None
    store.get_scheduled_prompts.assert_awaited()


async def test_run_loop_error_branch(store, monkeypatch):
    store.get_scheduled_prompts.side_effect = None
    s = PromptScheduler(store)
    s.running = True

    # Force an error inside the try (before the normal sleep) via _sync_calendar.
    async def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(s, "_sync_calendar", boom)
    monkeypatch.setattr(s, "_process_scheduled", AsyncMock())

    sleeps = {"n": 0}

    async def fake_sleep(_):
        sleeps["n"] += 1
        s.running = False  # exit loop cleanly after the error-branch sleep

    monkeypatch.setattr(sched.asyncio, "sleep", fake_sleep)
    await s._run_loop()
    assert sleeps["n"] == 1
