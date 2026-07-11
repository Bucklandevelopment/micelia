"""
Tests for EntireSessionService (app.services.entire_session).

Wrapper around the ``entire`` CLI for agent-session traceability. Two external
boundaries, both isolated here (no real binary, no subprocess, no network):

  - **``shutil.which("entire")``** — the ``is_available`` property probes the PATH
    once and caches the result in ``_entire_available``. We either force the cache
    directly (``_svc(available=...)``) or patch ``entire_session.shutil.which`` to
    exercise the real detection branch (the info-log fork at lines 27-33).
  - **``asyncio.create_subprocess_exec``** (inside ``_run_entire``) — patched with a
    factory returning a fake proc whose ``communicate`` is an ``AsyncMock``
    ``(stdout, stderr)`` and whose ``returncode`` is scriptable, so ``_run_entire``
    happy (rc 0 -> decoded stdout) and error (rc != 0 -> ``RuntimeError``) run without
    ever spawning a process.

``asyncio_mode = auto`` (pyproject) -> ``async def test_*`` needs no marker.

Covers: is_available (detect True/False + cache), start_session (unavailable /
available happy / entire raises -> swallowed / field shape / metadata default),
checkpoint (missing session no-op / in-memory only / entire happy + except / summary
truncation + None), end_session (missing no-op / happy with+without entire_session_id
/ except), get_sessions (desc order + limit/offset), get_session (present/absent),
get_sessions_for_prompt (filter + order), get_status (active/total counts), _run_entire
(rc 0 / rc != 0 -> RuntimeError), _trim_sessions (evicts oldest over cap), and the
``get_entire_service`` singleton.
"""

from unittest.mock import AsyncMock

import pytest

import app.services.entire_session as es
from app.services.entire_session import EntireSessionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Order-independence: reset the module-level singleton around each test."""
    es._entire_service = None
    yield
    es._entire_service = None


def _svc(available=None):
    """Build a service, optionally forcing the cached availability flag."""
    svc = EntireSessionService()
    if available is not None:
        svc._entire_available = available
    return svc


class _FakeProc:
    """Stand-in for the object returned by ``create_subprocess_exec``."""

    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.communicate = AsyncMock(return_value=(stdout, stderr))


def _patch_subprocess(monkeypatch, proc):
    """Patch ``create_subprocess_exec`` to return ``proc`` and capture the argv."""
    captured = {}

    async def _fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return proc

    monkeypatch.setattr(es.asyncio, "create_subprocess_exec", _fake_exec)
    return captured


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


def test_is_available_detects_present(monkeypatch):
    monkeypatch.setattr(es.shutil, "which", lambda name: "/usr/local/bin/entire")
    svc = EntireSessionService()
    assert svc.is_available is True
    assert svc._entire_available is True


def test_is_available_detects_absent(monkeypatch):
    monkeypatch.setattr(es.shutil, "which", lambda name: None)
    svc = EntireSessionService()
    assert svc.is_available is False
    assert svc._entire_available is False


def test_is_available_caches_after_first_probe(monkeypatch):
    calls = []

    def _which(name):
        calls.append(name)
        return None

    monkeypatch.setattr(es.shutil, "which", _which)
    svc = EntireSessionService()
    assert svc.is_available is False
    assert svc.is_available is False  # second access uses the cache
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# start_session
# ---------------------------------------------------------------------------


async def test_start_session_unavailable_in_memory_only(monkeypatch):
    svc = _svc(available=False)
    # create_subprocess_exec must never be called when entire is unavailable
    monkeypatch.setattr(
        es.asyncio, "create_subprocess_exec",
        AsyncMock(side_effect=AssertionError("must not spawn")),
    )
    sid = await svc.start_session("prompt-123", workflow_name="wf", run_id="r1")
    session = svc._sessions[sid]
    assert session["session_id"] == sid
    assert session["prompt_id"] == "prompt-123"
    assert session["workflow_name"] == "wf"
    assert session["run_id"] == "r1"
    assert session["status"] == "active"
    assert session["checkpoints"] == []
    assert session["metadata"] == {}
    assert session["entire_session_id"] is None
    assert session["ended_at"] is None


async def test_start_session_available_happy_sets_entire_id(monkeypatch):
    svc = _svc(available=True)
    proc = _FakeProc(returncode=0, stdout=b"  entire-abc\n")
    captured = _patch_subprocess(monkeypatch, proc)
    sid = await svc.start_session("prompt-xyz789")
    assert svc._sessions[sid]["entire_session_id"] == "entire-abc"
    # name is derived from the first 8 chars of the prompt id
    assert "--name" in captured["args"]
    assert "idm-prompt-x" in captured["args"]


async def test_start_session_available_entire_raises_is_swallowed(monkeypatch):
    svc = _svc(available=True)

    async def _boom(*a, **k):
        raise RuntimeError("cli down")

    monkeypatch.setattr(es.asyncio, "create_subprocess_exec", _boom)
    sid = await svc.start_session("p")
    # session still created, entire id stays None
    assert sid in svc._sessions
    assert svc._sessions[sid]["entire_session_id"] is None


async def test_start_session_custom_metadata_preserved():
    svc = _svc(available=False)
    meta = {"origin": "test", "n": 3}
    sid = await svc.start_session("p", metadata=meta)
    assert svc._sessions[sid]["metadata"] == meta


async def test_start_session_trims(monkeypatch):
    svc = _svc(available=False)
    svc._max_stored = 2
    ids = [await svc.start_session(f"p{i}") for i in range(4)]
    # only the cap survives; the oldest were evicted
    assert len(svc._sessions) == 2
    assert ids[0] not in svc._sessions
    assert ids[-1] in svc._sessions


# ---------------------------------------------------------------------------
# checkpoint
# ---------------------------------------------------------------------------


async def test_checkpoint_missing_session_noop():
    svc = _svc(available=False)
    # should simply return without raising
    await svc.checkpoint("nope", "agent", "act")


async def test_checkpoint_in_memory_only_when_no_entire_id():
    svc = _svc(available=True)
    sid = await svc.start_session("p")  # available but no entire_session_id set
    await svc.checkpoint(sid, "agentA", "did-thing", output_summary="hello")
    cps = svc._sessions[sid]["checkpoints"]
    assert len(cps) == 1
    assert cps[0]["agent"] == "agentA"
    assert cps[0]["action"] == "did-thing"
    assert cps[0]["output_summary"] == "hello"


async def test_checkpoint_calls_entire_when_available_and_tracked(monkeypatch):
    svc = _svc(available=True)
    sid = await svc.start_session("p")
    svc._sessions[sid]["entire_session_id"] = "entire-1"
    proc = _FakeProc(returncode=0, stdout=b"ok")
    captured = _patch_subprocess(monkeypatch, proc)
    await svc.checkpoint(sid, "agentB", "step")
    assert "checkpoint" in captured["args"]
    assert "--message" in captured["args"]
    assert "agentB:step" in captured["args"]


async def test_checkpoint_entire_failure_swallowed(monkeypatch):
    svc = _svc(available=True)
    sid = await svc.start_session("p")
    svc._sessions[sid]["entire_session_id"] = "entire-1"

    async def _boom(*a, **k):
        raise RuntimeError("checkpoint failed")

    monkeypatch.setattr(es.asyncio, "create_subprocess_exec", _boom)
    await svc.checkpoint(sid, "agentC", "step")
    # checkpoint still appended in-memory despite the CLI failure
    assert len(svc._sessions[sid]["checkpoints"]) == 1


async def test_checkpoint_truncates_summary():
    svc = _svc(available=False)
    sid = await svc.start_session("p")
    await svc.checkpoint(sid, "a", "x", output_summary="z" * 900)
    assert len(svc._sessions[sid]["checkpoints"][0]["output_summary"]) == 500


async def test_checkpoint_none_summary():
    svc = _svc(available=False)
    sid = await svc.start_session("p")
    await svc.checkpoint(sid, "a", "x", output_summary=None)
    assert svc._sessions[sid]["checkpoints"][0]["output_summary"] is None


# ---------------------------------------------------------------------------
# end_session
# ---------------------------------------------------------------------------


async def test_end_session_missing_noop():
    svc = _svc(available=False)
    await svc.end_session("nope")  # no raise


async def test_end_session_happy_without_entire_id():
    svc = _svc(available=False)
    sid = await svc.start_session("p")
    await svc.end_session(sid, status="failed")
    session = svc._sessions[sid]
    assert session["status"] == "failed"
    assert session["ended_at"] is not None


async def test_end_session_default_status_completed():
    svc = _svc(available=False)
    sid = await svc.start_session("p")
    await svc.end_session(sid)
    assert svc._sessions[sid]["status"] == "completed"


async def test_end_session_calls_entire_when_tracked(monkeypatch):
    svc = _svc(available=True)
    sid = await svc.start_session("p")
    svc._sessions[sid]["entire_session_id"] = "entire-1"
    proc = _FakeProc(returncode=0, stdout=b"")
    captured = _patch_subprocess(monkeypatch, proc)
    await svc.end_session(sid)
    assert "session" in captured["args"]
    assert "end" in captured["args"]


async def test_end_session_entire_failure_swallowed(monkeypatch):
    svc = _svc(available=True)
    sid = await svc.start_session("p")
    svc._sessions[sid]["entire_session_id"] = "entire-1"

    async def _boom(*a, **k):
        raise RuntimeError("end failed")

    monkeypatch.setattr(es.asyncio, "create_subprocess_exec", _boom)
    await svc.end_session(sid)
    assert svc._sessions[sid]["status"] == "completed"


# ---------------------------------------------------------------------------
# getters
# ---------------------------------------------------------------------------


async def test_get_sessions_desc_order_and_paging():
    svc = _svc(available=False)
    ids = []
    for i in range(3):
        sid = await svc.start_session(f"p{i}")
        # force distinct, monotonically increasing started_at for deterministic order
        svc._sessions[sid]["started_at"] = f"2026-07-11T00:00:0{i}"
        ids.append(sid)
    result = svc.get_sessions(limit=2, offset=0)
    assert [s["session_id"] for s in result] == [ids[2], ids[1]]
    # offset skips the newest
    assert [s["session_id"] for s in svc.get_sessions(limit=1, offset=1)] == [ids[1]]


async def test_get_session_present_and_absent():
    svc = _svc(available=False)
    sid = await svc.start_session("p")
    assert svc.get_session(sid)["session_id"] == sid
    assert svc.get_session("missing") is None


async def test_get_sessions_for_prompt_filters_and_orders():
    svc = _svc(available=False)
    a1 = await svc.start_session("promptA")
    svc._sessions[a1]["started_at"] = "2026-07-11T00:00:01"
    b1 = await svc.start_session("promptB")
    svc._sessions[b1]["started_at"] = "2026-07-11T00:00:02"
    a2 = await svc.start_session("promptA")
    svc._sessions[a2]["started_at"] = "2026-07-11T00:00:03"
    result = svc.get_sessions_for_prompt("promptA")
    assert [s["session_id"] for s in result] == [a2, a1]
    assert b1 not in [s["session_id"] for s in result]


async def test_get_status_counts():
    svc = _svc(available=False)
    active = await svc.start_session("p1")
    done = await svc.start_session("p2")
    await svc.end_session(done)
    status = svc.get_status()
    assert status["total_sessions"] == 2
    assert status["active_sessions"] == 1
    assert status["entire_available"] is False
    assert active in svc._sessions


# ---------------------------------------------------------------------------
# _run_entire
# ---------------------------------------------------------------------------


async def test_run_entire_success_returns_stdout(monkeypatch):
    svc = _svc(available=True)
    proc = _FakeProc(returncode=0, stdout=b"result-text\n")
    _patch_subprocess(monkeypatch, proc)
    out = await svc._run_entire("session", "start")
    assert out == "result-text\n"


async def test_run_entire_nonzero_raises(monkeypatch):
    svc = _svc(available=True)
    proc = _FakeProc(returncode=1, stdout=b"", stderr=b"boom")
    _patch_subprocess(monkeypatch, proc)
    with pytest.raises(RuntimeError, match="entire failed: boom"):
        await svc._run_entire("session", "start")


# ---------------------------------------------------------------------------
# _trim_sessions
# ---------------------------------------------------------------------------


def test_trim_sessions_evicts_oldest():
    svc = _svc(available=False)
    svc._max_stored = 2
    for i in range(4):
        svc._sessions[f"s{i}"] = {"started_at": f"2026-07-11T00:00:0{i}"}
    svc._trim_sessions()
    assert set(svc._sessions) == {"s2", "s3"}


def test_trim_sessions_under_cap_noop():
    svc = _svc(available=False)
    svc._max_stored = 10
    svc._sessions = {"a": {"started_at": "x"}}
    svc._trim_sessions()
    assert set(svc._sessions) == {"a"}


# ---------------------------------------------------------------------------
# singleton
# ---------------------------------------------------------------------------


def test_get_entire_service_singleton():
    first = es.get_entire_service()
    second = es.get_entire_service()
    assert first is second
    assert isinstance(first, EntireSessionService)
