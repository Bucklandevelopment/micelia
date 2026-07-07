"""
Tests for PromptPrioritizationAgent.

Pure helpers (_calculate_priority, _find_group) are tested directly; the async
pipeline (_classify_captured, _process_pending, _run_loop) uses a mocked store,
event bus and taxonomy runner. datetime is patched where time-relative branches
are exercised. No infra.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import prompt_agent as pa
from app.services.prompt_agent import PromptPrioritizationAgent

FIXED_NOW = datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)


class _FakeDT:
    """datetime stand-in: fixed now(), real fromisoformat()."""

    @staticmethod
    def now(tz=None):
        return FIXED_NOW

    @staticmethod
    def fromisoformat(s):
        return datetime.fromisoformat(s)


@pytest.fixture
def agent():
    return PromptPrioritizationAgent(AsyncMock())


# --------------------------------------------------------------------------
# _calculate_priority (pure)
# --------------------------------------------------------------------------

def test_priority_base_default(agent):
    assert agent._calculate_priority({}) == 5


@pytest.mark.parametrize("cat,expected", [("work", 7), ("plan", 6), ("routine", 4), ("xyz", 5)])
def test_priority_category_boost(agent, cat, expected):
    assert agent._calculate_priority({"priority": 5, "category": cat}) == expected


@pytest.mark.parametrize("tag,delta", [("urgent", 5), ("urgente", 5), ("important", 3), ("baja", -3)])
def test_priority_tag_boost(agent, tag, delta):
    base = agent._calculate_priority({"priority": 4})
    assert agent._calculate_priority({"priority": 4, "tags": [tag]}) == max(0, min(10, base + delta))


def test_priority_clamped_to_range(agent):
    assert agent._calculate_priority({"priority": 9, "tags": ["urgent", "important"]}) == 10
    assert agent._calculate_priority({"priority": 0, "tags": ["low"]}) == 0


def test_priority_scheduled_soon(agent, monkeypatch):
    monkeypatch.setattr(pa, "datetime", _FakeDT)
    soon = (FIXED_NOW + timedelta(seconds=120)).isoformat()
    hour = (FIXED_NOW + timedelta(minutes=45)).isoformat()
    assert agent._calculate_priority({"priority": 3, "scheduled_at": soon}) == 8  # +5
    assert agent._calculate_priority({"priority": 3, "scheduled_at": hour}) == 6  # +3


def test_priority_invalid_scheduled_swallowed(agent, monkeypatch):
    monkeypatch.setattr(pa, "datetime", _FakeDT)
    assert agent._calculate_priority({"priority": 5, "scheduled_at": "not-a-date"}) == 5


def test_priority_age_boost(agent, monkeypatch):
    monkeypatch.setattr(pa, "datetime", _FakeDT)
    old = (FIXED_NOW - timedelta(hours=100)).isoformat()  # >72h -> +1 +2
    assert agent._calculate_priority({"priority": 5, "created_at": old}) == 8


def test_priority_invalid_created_swallowed(agent, monkeypatch):
    monkeypatch.setattr(pa, "datetime", _FakeDT)
    assert agent._calculate_priority({"priority": 5, "created_at": "bad"}) == 5


# --------------------------------------------------------------------------
# _find_group (pure)
# --------------------------------------------------------------------------

def test_find_group_uses_existing_correlation(agent):
    assert agent._find_group({"correlation_id": "abc"}, []) == "abc"


def test_find_group_no_tags_returns_none(agent):
    assert agent._find_group({"prompt_id": "p1"}, []) is None


def test_find_group_shared_tags_creates_group(agent):
    p1 = {"prompt_id": "p1", "tags": ["a", "b", "c"]}
    p2 = {"prompt_id": "p2", "tags": ["a", "b"]}
    gid = agent._find_group(p1, [p1, p2])
    assert gid is not None


def test_find_group_reuses_other_correlation(agent):
    p1 = {"prompt_id": "p1", "tags": ["a", "b"]}
    p2 = {"prompt_id": "p2", "tags": ["a", "b"], "correlation_id": "shared"}
    assert agent._find_group(p1, [p1, p2]) == "shared"


def test_find_group_insufficient_overlap_returns_none(agent):
    p1 = {"prompt_id": "p1", "tags": ["a", "x"]}
    p2 = {"prompt_id": "p2", "tags": ["a", "y"]}
    assert agent._find_group(p1, [p1, p2]) is None


# --------------------------------------------------------------------------
# _process_pending
# --------------------------------------------------------------------------

async def test_process_pending_empty_sets_scan(agent):
    agent._store.get_pending_prompts.return_value = []
    await agent._process_pending()
    assert agent.last_pending_count == 0
    assert agent.last_scan is not None
    agent._store.update_prompt.assert_not_called()


async def test_process_pending_queues_and_publishes():
    store = AsyncMock()
    bus = AsyncMock()
    store.get_pending_prompts.return_value = [
        {"prompt_id": "p1", "category": "work", "priority": 5, "tags": ["urgent"]},
    ]
    agent = PromptPrioritizationAgent(store, event_bus=bus)
    await agent._process_pending()
    store.update_prompt.assert_awaited_once()
    kwargs = store.update_prompt.await_args.kwargs
    assert kwargs["status"] == "queued"
    assert kwargs["priority"] == 10  # 5 +2(work) +5(urgent) clamped
    bus.publish.assert_awaited_once()


async def test_process_pending_event_error_swallowed():
    store = AsyncMock()
    bus = AsyncMock()
    bus.publish.side_effect = RuntimeError("bus down")
    store.get_pending_prompts.return_value = [
        {"prompt_id": "p1", "category": "note", "priority": 5, "tags": []},
    ]
    agent = PromptPrioritizationAgent(store, event_bus=bus)
    await agent._process_pending()  # must not raise
    store.update_prompt.assert_awaited_once()


# --------------------------------------------------------------------------
# _classify_captured
# --------------------------------------------------------------------------

async def test_classify_captured_no_capability_returns():
    store = MagicMock(spec=["get_pending_prompts", "update_prompt"])
    agent = PromptPrioritizationAgent(store)
    await agent._classify_captured()  # store lacks get_captured_prompts -> early return


async def test_classify_captured_empty_returns(agent):
    agent._store.get_captured_prompts.return_value = []
    await agent._classify_captured()
    agent._store.update_prompt.assert_not_called()


async def test_classify_captured_applies_taxonomy(agent, monkeypatch):
    agent._store.get_captured_prompts.return_value = [
        {"prompt_id": "p1", "tags": ["keep"]},
    ]
    runner = MagicMock()
    runner.run_taxonomy = AsyncMock(return_value={"data": {
        "category": "work", "tags": ["new"], "priority": 8,
        "workflow": "reviewed_execute", "provider_policy": "paid-for-work",
        "needs_staging": True,
    }})
    monkeypatch.setattr(pa, "get_prompt_os_runner", lambda: runner)
    await agent._classify_captured()
    kwargs = agent._store.update_prompt.await_args.kwargs
    assert kwargs["category"] == "work"
    assert kwargs["priority"] == 8
    assert set(kwargs["tags"]) == {"keep", "new"}
    assert kwargs["status"] == "pending"


async def test_classify_captured_taxonomy_failure_falls_back(agent, monkeypatch):
    agent._store.get_captured_prompts.return_value = [{"prompt_id": "p1"}]
    runner = MagicMock()
    runner.run_taxonomy = AsyncMock(side_effect=RuntimeError("llm down"))
    monkeypatch.setattr(pa, "get_prompt_os_runner", lambda: runner)
    await agent._classify_captured()
    agent._store.update_prompt.assert_awaited_once_with("p1", status="pending")


# --------------------------------------------------------------------------
# lifecycle
# --------------------------------------------------------------------------

async def test_start_and_stop(agent):
    await agent.start()
    assert agent.running is True
    assert agent._task is not None
    # double start is a no-op (same task)
    first = agent._task
    await agent.start()
    assert agent._task is first
    await agent.stop()
    assert agent.running is False
    assert agent._task.done()


async def test_run_loop_one_cycle_then_cancel(agent, monkeypatch):
    agent.running = True
    agent._store.get_captured_prompts.return_value = []
    agent._store.get_pending_prompts.return_value = []

    calls = {"n": 0}

    async def fake_sleep(_):
        calls["n"] += 1
        raise asyncio.CancelledError

    monkeypatch.setattr(pa.asyncio, "sleep", fake_sleep)
    await agent._run_loop()
    assert calls["n"] == 1
    agent._store.get_pending_prompts.assert_awaited()


async def test_run_loop_error_branch(agent, monkeypatch):
    agent.running = True
    agent._store.get_captured_prompts.side_effect = RuntimeError("boom")

    sleeps = {"n": 0}

    async def fake_sleep(_):
        # First (and only) sleep is the error-branch recovery sleep; stop the
        # loop cleanly so it exits via the `while self.running` condition.
        sleeps["n"] += 1
        agent.running = False

    monkeypatch.setattr(pa.asyncio, "sleep", fake_sleep)
    await agent._run_loop()  # RuntimeError caught, error-branch sleep hit, then exits
    assert sleeps["n"] == 1
